# src/agent.py

import logging
from langgraph.graph import StateGraph, END
from state import AgentState
from tools.youtube_tools import search_videos_node, summarize_videos_node
from tools.reporting_tools import generate_report_node, send_email_node
from tools.router_tools import plan_research_node, router_node
from tools.reddit_tools import search_reddit_node
from tools.research_tools import search_web_node, search_wiki_node, search_arxiv_node, search_scholar_node, search_github_node, search_hn_node, search_so_node
from tools.synthesis_tools import consolidate_research_node

logger = logging.getLogger(__name__)

def initialize_state_node(state: AgentState) -> dict:
    """Ensure all state fields are initialized with default values."""
    logger.info("Initializing agent state...")
    defaults = {
        "topic": state.get("topic", ""),
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
        "consolidated_summary": state.get("consolidated_summary", ""),
        "bibliography": state.get("bibliography", []),
        "pdf_path": state.get("pdf_path", ""),
        "report": state.get("report", ""),
        "messages": state.get("messages", []),
        "research_plan": state.get("research_plan", []),
        "next_node": state.get("next_node", ""),
        "iteration_count": state.get("iteration_count", 0)
    }
    return defaults

# Helper for conditional routing
def route_research(state: AgentState):
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
        "youtube": "search_videos"
    }
    
    return mapping.get(current, "consolidate_research")

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

# Add edges - define execution flow
logger.info("Connecting nodes with edges...")
workflow.set_entry_point("initialize_state")
workflow.add_edge("initialize_state", "plan_research")

# Dynamic navigation after planning
workflow.add_conditional_edges(
    "plan_research", 
    route_research,
    {
        "search_wiki": "search_wiki",
        "search_web": "search_web",
        "search_arxiv": "search_arxiv",
        "search_scholar": "search_scholar",
        "search_github": "search_github",
        "search_hn": "search_hn",
        "search_so": "search_so",
        "search_videos": "search_videos",
        "consolidate_research": "consolidate_research"
    }
)

# Every search node needs to update the state and go to the next node
search_nodes = ["search_wiki", "search_web", "search_arxiv", "search_scholar", "search_github", "search_hn", "search_so", "search_videos", "search_reddit"]

for node in search_nodes:
    if node == "search_videos":
        # Special case: search_videos goes to summarize_videos first
        workflow.add_edge("search_videos", "summarize_videos")
        workflow.add_conditional_edges(
            "summarize_videos", 
            route_research,
            {
                "search_wiki": "search_wiki",
                "search_web": "search_web",
                "search_arxiv": "search_arxiv",
                "search_scholar": "search_scholar",
                "search_github": "search_github",
                "search_hn": "search_hn",
                "search_so": "search_so",
                "search_videos": "search_videos",
                "search_reddit": "search_reddit",
                "consolidate_research": "consolidate_research"
            }
        )
    else:
        workflow.add_conditional_edges(
            node, 
            route_research,
            {
                "search_wiki": "search_wiki",
                "search_web": "search_web",
                "search_arxiv": "search_arxiv",
                "search_scholar": "search_scholar",
                "search_github": "search_github",
                "search_hn": "search_hn",
                "search_so": "search_so",
                "search_videos": "search_videos",
                "search_reddit": "search_reddit",
                "consolidate_research": "consolidate_research"
            }
        )

workflow.add_edge("consolidate_research", "generate_report")
workflow.add_edge("generate_report", "send_email")
workflow.add_edge("send_email", END)

# Compile the agent
logger.info("Compiling agent...")
app = workflow.compile()
logger.info("Agent compiled successfully!")