import os
import logging
from typing import List
from state import AgentState
from tools.router_tools import update_next_node

logger = logging.getLogger(__name__)

def search_reddit_node(state: AgentState) -> dict:
    """Search Reddit for community discussions and opinions."""
    logger.info("Starting Reddit search...")
    topic = state["topic"]
    
    # Prioritize config from settings, fallback to env
    try:
        from config import settings
        tavily_key = settings.tavily_api_key
        max_results = settings.max_results_per_source
    except:
        tavily_key = None
        max_results = 3
        
    if not tavily_key:
        tavily_key = os.getenv("TAVILY_API_KEY")
    
    results = []
    
    try:
        if tavily_key:
            from langchain_community.tools.tavily_search import TavilySearchResults
            search = TavilySearchResults(k=max_results)
            res = search.run(f"{topic} site:reddit.com")
            results = res
        else:
            # Fallback to DuckDuckGo
            from langchain_community.tools import DuckDuckGoSearchRun
            search = DuckDuckGoSearchRun()
            res_text = search.run(f"{topic} reddit")
            results = [{"content": res_text, "url": "Reddit (via DDG)"}]
            
        logger.info(f"Reddit search completed with {len(results)} results")
        
    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        results = []
        
    return {"reddit_research": results, "next_node": update_next_node(state, "reddit")}
