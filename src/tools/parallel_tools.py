# src/tools/parallel_tools.py

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..state import AgentState

logger = logging.getLogger(__name__)


def _youtube_combined_node(state: AgentState) -> dict:
    """Run YouTube search + summarize sequentially (summarize depends on search)."""
    from .youtube_tools import search_videos_node, summarize_videos_node

    search_result = search_videos_node(state)
    # Merge search results into a copy of state for the summarize step
    merged_state = {**state, **search_result}
    summarize_result = summarize_videos_node(merged_state)
    # Combine both results
    combined = {}
    combined.update(search_result)
    combined.update(summarize_result)
    return combined


def parallel_search_node(state: AgentState) -> dict:
    """Execute all planned research sources in parallel."""
    from .research_tools import (
        search_web_node, search_wiki_node, search_arxiv_node,
        search_scholar_node, search_github_node, search_hn_node, search_so_node
    )
    from .reddit_tools import search_reddit_node
    from .rag_tools import local_rag_node

    plan = state.get("research_plan", [])
    logger.info(f"Parallel search starting for sources: {plan}")

    source_functions = {
        "web": search_web_node,
        "wiki": search_wiki_node,
        "arxiv": search_arxiv_node,
        "scholar": search_scholar_node,
        "github": search_github_node,
        "hn": search_hn_node,
        "so": search_so_node,
        "reddit": search_reddit_node,
        "local_rag": local_rag_node,
        "youtube": _youtube_combined_node,
    }

    combined = {}
    futures_map = {}

    with ThreadPoolExecutor(max_workers=len(plan) or 1) as executor:
        for source_name in plan:
            fn = source_functions.get(source_name)
            if fn:
                future = executor.submit(fn, state)
                futures_map[future] = source_name
            else:
                logger.warning(f"Unknown source in plan: {source_name}")

        for future in as_completed(futures_map):
            source_name = futures_map[future]
            try:
                result = future.result()
                combined.update(result)
                logger.info(f"Source '{source_name}' completed successfully")
            except Exception as e:
                logger.error(f"Source '{source_name}' failed: {e}")

    # Set next_node to END so consolidation follows
    combined["next_node"] = "END"
    logger.info(f"Parallel search completed. Keys: {list(combined.keys())}")
    return combined
