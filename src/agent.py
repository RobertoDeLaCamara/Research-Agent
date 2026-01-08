# src/agent.py

import logging
from langgraph.graph import StateGraph, END
from state import AgentState
from tools.youtube_tools import search_videos_node, summarize_videos_node
from tools.reporting_tools import generate_report_node, send_email_node
from tools.research_tools import search_web_node, search_wiki_node, search_arxiv_node, search_scholar_node, search_github_node, search_hn_node, search_so_node
from tools.synthesis_tools import consolidate_research_node

logger = logging.getLogger(__name__)

# Create workflow graph
workflow = StateGraph(AgentState)

# Add nodes
logger.info("Defining workflow nodes...")
workflow.add_node("search_videos", search_videos_node)
workflow.add_node("summarize_videos", summarize_videos_node)
workflow.add_node("search_web", search_web_node)
workflow.add_node("search_wiki", search_wiki_node)
workflow.add_node("search_arxiv", search_arxiv_node)
workflow.add_node("search_scholar", search_scholar_node)
workflow.add_node("search_github", search_github_node)
workflow.add_node("search_hn", search_hn_node)
workflow.add_node("search_so", search_so_node)
workflow.add_node("consolidate_research", consolidate_research_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("send_email", send_email_node)

# Add edges - define execution flow
logger.info("Connecting nodes with edges...")
workflow.set_entry_point("search_wiki")  # Start with Wikipedia for context
workflow.add_edge("search_wiki", "search_web")
workflow.add_edge("search_web", "search_arxiv")
workflow.add_edge("search_arxiv", "search_scholar")
workflow.add_edge("search_scholar", "search_github")
workflow.add_edge("search_github", "search_hn")
workflow.add_edge("search_hn", "search_so")
workflow.add_edge("search_so", "search_videos")
workflow.add_edge("search_videos", "summarize_videos")
workflow.add_edge("summarize_videos", "consolidate_research")
workflow.add_edge("consolidate_research", "generate_report")
workflow.add_edge("generate_report", "send_email")
workflow.add_edge("send_email", END)

# Compile the agent
logger.info("Compiling agent...")
app = workflow.compile()
logger.info("Agent compiled successfully!")