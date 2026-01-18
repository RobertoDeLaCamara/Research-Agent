# src/agent.py

import logging
from langgraph.graph import StateGraph, END
from .state import AgentState
from .tools.youtube_tools import search_videos_node, summarize_videos_node
from .tools.reporting_tools import generate_report_node, send_email_node
from .tools.router_tools import plan_research_node, router_node, evaluate_research_node
from .tools.reddit_tools import search_reddit_node
from .tools.research_tools import (
    search_web_node, search_wiki_node, search_arxiv_node, 
    search_scholar_node, search_github_node, search_hn_node, search_so_node
)
from .tools.synthesis_tools import consolidate_research_node
from .tools.chat_tools import chat_node
from .tools.rag_tools import local_rag_node

logger = logging.getLogger(__name__)

def initialize_state_node(state: AgentState) -> dict:
    """Ensure all state fields are initialized with default values."""
    logger.info("Initializing agent state...")
    
    # Initialize DB for Phase 6
    from .db_manager import init_db, save_session
    init_db()
    
    defaults = {
        "topic": state.get("topic", ""),
        "original_topic": state.get("original_topic", state.get("topic", "")),
        "video_urls": state.get("video_urls", []),
        "video_metadata": state.get("video_metadata", []),
        "summaries": state.get("summaries", []),
        "web_research": state.get("web_research", []),
        "wiki_research": state.get("wiki_research", []),
        "arxiv_research": state.get("arxiv_research", []),
        "github_research": state.get("github_research", []),
        "scholar_research": state.get("scholar_research", []),
        "hn_research": state.get("hn_research", []),
        "so_research": state.get("so_research", []),
        "reddit_research": state.get("reddit_research", []),
        "local_research": state.get("local_research", []),
        "consolidated_summary": state.get("consolidated_summary", ""),
        "bibliography": state.get("bibliography", []),
        "pdf_path": state.get("pdf_path", ""),
        "report": state.get("report", ""),
        "messages": state.get("messages", []),
        "research_plan": state.get("research_plan", []),
        "next_node": state.get("next_node", ""),
        "iteration_count": state.get("iteration_count", 0),
        "last_email_hash": state.get("last_email_hash", ""),
        "research_depth": state.get("research_depth", "standard"),
        "persona": state.get("persona", "general"),
        "evaluation_report": state.get("evaluation_report", ""),
        "queries": state.get("queries", {}),
        "source_metadata": state.get("source_metadata", {})
    }
    
    # Optional: Save initial state as start of session
    # save_session(defaults["topic"], defaults["persona"], defaults)
    
    return defaults

# Helper for conditional routing
def route_research(state: AgentState) -> str:
    """LangGraph conditional edge to determine where to go next."""
    plan = state.get("research_plan", [])
    current = state.get("next_node")
    
    if not plan or current == "END":
        return "consolidate_research"
        
    # Mapping for LangGraph node names
    mapping = {
        "wiki": "search_wiki",
        "web": "search_web",
        "arxiv": "search_arxiv",
        "scholar": "search_scholar",
        "github": "search_github",
        "hn": "search_hn",
        "so": "search_so",
        "youtube": "search_videos",
        "reddit": "search_reddit",
        "local_rag": "local_rag"
    }
    
    return mapping.get(current, "consolidate_research")

def route_chat(state: AgentState) -> str:
    """Decide whether to continue chatting or do more research."""
    if not state["messages"]:
        return "send_email"
        
    last_msg = state["messages"][-1]
    last_content = last_msg.content
    
    # 1. If it's a HumanMessage, search for research intent
    from langchain_core.messages import HumanMessage
    if isinstance(last_msg, HumanMessage):
        from .config import settings
        text = last_content.lower()
        if any(kw in text for kw in settings.research_trigger_keywords):
            return "re_plan"
            
    # 2. If it's an AIMessage, ONLY loop back if it explicitly has the trigger tag
    # This prevents loops from the AI saying "I finished the investigation"
    if "INVESTIGACIÓN:" in last_content:
        # Check that it's actually proposing new research, not just using the word
        # In chat_node, we prompt the AI to use "INVESTIGACIÓN: [topic]"
        return "re_plan"
        
    return "send_email"

def save_db_node(state: AgentState) -> dict:
    """Save the final state to the database."""
    print("\n--- 💾 NODO: GUARDANDO SESIÓN ---")
    from .db_manager import save_session
    try:
        topic = state.get("topic", "Sin Tema")
        persona = state.get("persona", "General")
        save_session(topic, persona, state)
        print("✅ Sesión guardada en base de datos.")
    except Exception as e:
        print(f"⚠️ Error al guardar sesión: {e}")
    return {} # No state update needed

# Create workflow graph
workflow = StateGraph(AgentState)

# Add nodes
logger.info("Defining workflow nodes...")
workflow.add_node("initialize_state", initialize_state_node)
workflow.add_node("plan_research", plan_research_node)
workflow.add_node("search_videos", search_videos_node)
workflow.add_node("summarize_videos", summarize_videos_node)
workflow.add_node("search_web", search_web_node)
workflow.add_node("search_wiki", search_wiki_node)
workflow.add_node("search_arxiv", search_arxiv_node)
workflow.add_node("search_scholar", search_scholar_node)
workflow.add_node("search_github", search_github_node)
workflow.add_node("search_hn", search_hn_node)
workflow.add_node("search_so", search_so_node)
workflow.add_node("search_reddit", search_reddit_node)
workflow.add_node("consolidate_research", consolidate_research_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("send_email", send_email_node)
workflow.add_node("save_db", save_db_node)
workflow.add_node("chat", chat_node)
workflow.add_node("evaluate_research", evaluate_research_node)
workflow.add_node("local_rag", local_rag_node)

# Add edges - define execution flow
logger.info("Connecting nodes with edges...")
workflow.set_entry_point("initialize_state")
workflow.add_edge("initialize_state", "plan_research")

# Dynamic navigation destinations
destinations = {
    "search_wiki": "search_wiki",
    "search_web": "search_web",
    "search_arxiv": "search_arxiv",
    "search_scholar": "search_scholar",
    "search_github": "search_github",
    "search_hn": "search_hn",
    "search_so": "search_so",
    "search_videos": "search_videos",
    "search_reddit": "search_reddit",
    "local_rag": "local_rag",
    "consolidate_research": "consolidate_research"
}

# Dynamic navigation after planning
workflow.add_conditional_edges("plan_research", route_research, destinations)

# Every search node needs to update the state and go to the next node
search_nodes = ["search_wiki", "search_web", "search_arxiv", "search_scholar", "search_github", "search_hn", "search_so", "search_videos", "search_reddit", "local_rag"]

for node in search_nodes:
    if node == "search_videos":
        workflow.add_edge("search_videos", "summarize_videos")
        workflow.add_conditional_edges("summarize_videos", route_research, destinations)
    else:
        workflow.add_conditional_edges(node, route_research, destinations)

workflow.add_edge("consolidate_research", "evaluate_research")

def route_evaluation(state: AgentState):
    """Route based on evaluation result."""
    return state.get("next_node", "END")

workflow.add_conditional_edges(
    "evaluate_research",
    route_evaluation,
    {
        "plan_research": "plan_research",
        "END": "generate_report"
    }
)

workflow.add_edge("generate_report", "send_email")

# Chat node is kept for manual interaction, but not as part of the automated sequence
workflow.add_conditional_edges(
    "chat",
    route_chat,
    {
        "re_plan": "plan_research",
        "send_email": "send_email"
    }
)

workflow.add_edge("send_email", "save_db")
workflow.add_edge("save_db", END)

# Compile the agent
logger.info("Compiling agent...")
app = workflow.compile()
logger.info("Agent compiled successfully!")