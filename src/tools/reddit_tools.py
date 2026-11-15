import logging
from ..credentials import get_credential
from ..state import AgentState
from .router_tools import update_next_node
from .source_loaders import duckduckgo_search

logger = logging.getLogger(__name__)


def search_reddit_node(state: AgentState) -> dict:
    """Search Reddit for community discussions and opinions."""
    logger.info("Starting Reddit search...")
    topic = state.get("topic", "")
    queries = state.get("queries", {})
    search_topic = queries.get("en", queries.get("es", topic))

    # Use depth-aware max results
    from ..utils import get_max_results
    max_results = get_max_results(state)

    tavily_key = get_credential("TAVILY_API_KEY")

    results = []

    try:
        import threading
        container = {"data": []}
        def run_reddit_search():
            if tavily_key:
                from tavily import TavilyClient
                tavily = TavilyClient(api_key=tavily_key)

                # Phase 7: Support for temporal filtering in Reddit
                time_range = state.get("time_range", None)
                if state.get("persona") == "news_editor" and not time_range:
                    time_range = "d"

                search_params = {
                    "query": f"{search_topic} site:reddit.com",
                    "search_depth": "advanced",
                    "max_results": max_results
                }
                if time_range:
                    search_params["time_range"] = time_range

                search_result = tavily.search(**search_params)
                tavily_results = search_result.get("results", [])

                # Re-format for the node
                container["data"] = [{"content": r.get("content"), "url": r.get("url"), "title": r.get("title")} for r in tavily_results]
            else:
                # Fallback to DuckDuckGo
                container["data"] = duckduckgo_search(f"{search_topic} reddit", max_results=max_results)

        thread = threading.Thread(target=run_reddit_search, daemon=True)
        thread.start()
        thread.join(timeout=15) # 15 seconds timeout
        if thread.is_alive():
            logger.warning("Reddit search timed out.")
        else:
            results = container["data"]

        logger.info(f"Reddit search completed with {len(results)} results")

    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        results = []

    return {"reddit_research": results, "next_node": update_next_node(state, "reddit"), "source_metadata": {"reddit": {"source_type": "community", "reliability": 2}}}
