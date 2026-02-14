# src/agent.py

import logging
from langgraph.graph import StateGraph, END
from .state import AgentState
from .tools.reporting_tools import generate_report_node, send_email_node
from .tools.router_tools import plan_research_node, evaluate_research_node
from .tools.synthesis_tools import consolidate_research_node
from .tools.chat_tools import chat_node
from .tools.parallel_tools import parallel_search_node

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

    return defaults

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
        return "re_plan"

    return "send_email"

def save_db_node(state: AgentState) -> dict:
    """Save the final state to the database."""
    logger.info("save_db_node_started")
    from .db_manager import save_session
    try:
        topic = state.get("topic", "Sin Tema")
        persona = state.get("persona", "General")
        save_session(topic, persona, state)
        logger.info("session_saved", topic=topic, persona=persona)
    except Exception as e:
        logger.error("session_save_failed", error=str(e))
    return {} # No state update needed

# Create workflow graph
workflow = StateGraph(AgentState)

# Add nodes
logger.info("Defining workflow nodes...")
workflow.add_node("initialize_state", initialize_state_node)
workflow.add_node("plan_research", plan_research_node)
workflow.add_node("parallel_search", parallel_search_node)
workflow.add_node("consolidate_research", consolidate_research_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("send_email", send_email_node)
workflow.add_node("save_db", save_db_node)
workflow.add_node("chat", chat_node)
workflow.add_node("evaluate_research", evaluate_research_node)

# Add edges - simplified parallel flow
logger.info("Connecting nodes with edges...")
workflow.set_entry_point("initialize_state")
workflow.add_edge("initialize_state", "plan_research")
workflow.add_edge("plan_research", "parallel_search")
workflow.add_edge("parallel_search", "consolidate_research")
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
