import logging
import re
from ..state import AgentState
from .router_tools import update_next_node
from .source_loaders import duckduckgo_search, is_bot_block_or_stub

logger = logging.getLogger(__name__)

# `time_range` values accepted in the state -> ddgs `timelimit`
TIME_RANGE_TO_TIMELIMIT = {
    "d": "d", "day": "d", "w": "w", "week": "w",
    "m": "m", "month": "m", "y": "y", "year": "y",
}

_REDDIT_MEDIA_URL_RE = re.compile(r"reddit\.com/(video|media|gallery)/|://(v|i)\.redd\.it/", re.I)
_WIFI_6GHZ_RE = re.compile(r"\b(6\s*ghz|wifi\s*6e?|wi-fi\s*6e?|canal\s*6)\b", re.I)
_CELLULAR_6G_RE = re.compile(r"\b6g\b", re.I)
_WIFI_QUERY_RE = re.compile(r"\b(wifi|wi-fi|6\s*ghz|router)\b", re.I)


def is_reddit_result_relevant(hit: dict, query: str = "") -> bool:
    """Filter out non-Reddit ad links, blocked stubs, media-only links, and WiFi 6GHz / off-topic posts."""
    if not isinstance(hit, dict):
        return False
    url = (hit.get("url") or "").strip()
    if url and "reddit.com" not in url.lower() and "redd.it" not in url.lower():
        return False
    content = (hit.get("content") or hit.get("snippet") or "").strip()
    title = (hit.get("title") or "").strip()
    if is_bot_block_or_stub(content, title):
        return False
    if _REDDIT_MEDIA_URL_RE.search(url):
        return False
    combined = f"{title} {content} {url}"
    # Disambiguate 6G mobile networks vs WiFi 6 / 6GHz band
    if _CELLULAR_6G_RE.search(query or "") and not _WIFI_QUERY_RE.search(query or ""):
        if _WIFI_6GHZ_RE.search(combined) and not _CELLULAR_6G_RE.search(combined):
            return False
    # If query contains strong technical anchors (6g, 3gpp, agentic), require at least one in the post
    query_anchors = [
        a for a in ("6g", "3gpp", "agentic", "agéntica", "agentica")
        if re.search(rf"\b{re.escape(a)}\b", (query or "").lower())
    ]
    if query_anchors:
        combined_lower = combined.lower()
        if not any(re.search(rf"\b{re.escape(a)}\b", combined_lower) for a in query_anchors):
            return False
    return True


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
                raw_hits = duckduckgo_search(
                    f"{search_topic} site:reddit.com", max_results=max_results, timelimit=timelimit
                )
                container["data"] = [
                    h for h in raw_hits if is_reddit_result_relevant(h, search_topic)
                ]
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
