import os
import logging
from typing import List
from state import AgentState
from tools.router_tools import update_next_node

logger = logging.getLogger(__name__)

def search_reddit_node(state: AgentState) -> dict:
    """Search Reddit for community discussions and opinions."""
    logger.info("Starting Reddit search...")
    topic = state.get("topic", "")
    queries = state.get("queries", {})
    search_topic = queries.get("en", queries.get("es", topic))
    
    # Use depth-aware max results
    from utils import get_max_results
    max_results = get_max_results(state)
    
    # Prioritize config from settings for API key
    try:
        from config import settings
        tavily_key = settings.tavily_api_key
    except:
        tavily_key = None
        
    if not tavily_key:
        tavily_key = os.getenv("TAVILY_API_KEY")
    
    results = []
    
    try:
        import threading
        def run_reddit_search():
            nonlocal results
            if tavily_key:
                from langchain_community.tools.tavily_search import TavilySearchResults
                search = TavilySearchResults(k=max_results)
                results = search.run(f"{search_topic} site:reddit.com")
            else:
                # Fallback to DuckDuckGo
                from langchain_community.tools import DuckDuckGoSearchRun
                search = DuckDuckGoSearchRun()
                res_text = search.run(f"{search_topic} reddit")
                results = [{"content": res_text, "url": "Reddit (via DDG)"}]
        
        thread = threading.Thread(target=run_reddit_search)
        thread.start()
        thread.join(timeout=15) # 15 seconds timeout
        if thread.is_alive():
            logger.warning("Reddit search timed out.")
            results = []
        
        logger.info(f"Reddit search completed with {len(results)} results")
        
    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        results = []
        
    return {"reddit_research": results, "next_node": update_next_node(state, "reddit")}
