import logging
from ..state import AgentState
from .router_tools import update_next_node
from .source_loaders import duckduckgo_search

logger = logging.getLogger(__name__)

# `time_range` values accepted in the state -> ddgs `timelimit`
TIME_RANGE_TO_TIMELIMIT = {
    "d": "d", "day": "d", "w": "w", "week": "w",
    "m": "m", "month": "m", "y": "y", "year": "y",
}


def search_reddit_node(state: AgentState) -> dict:
    """Search Reddit for community discussions and opinions."""
    logger.info("Starting Reddit search...")
    topic = state.get("topic", "")
    queries = state.get("queries", {})
    search_topic = queries.get("en", queries.get("es", topic))

    # Use depth-aware max results
    from ..utils import get_max_results
    max_results = get_max_results(state)

    results = []

    try:
        import threading
        container = {"data": []}
        def run_reddit_search():
            # Temporal filtering: an explicit time range wins; the news editor defaults to the last day
            time_range = state.get("time_range", None)
            if state.get("persona") == "news_editor" and not time_range:
                time_range = "d"
            timelimit = TIME_RANGE_TO_TIMELIMIT.get(time_range, "y")
            try:
                container["data"] = duckduckgo_search(
                    f"{search_topic} site:reddit.com", max_results=max_results, timelimit=timelimit
                )
            except Exception as e_inner:
                # Raised inside the worker thread, so the outer try would never see it
                logger.error(f"Reddit search failed: {e_inner}")

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
