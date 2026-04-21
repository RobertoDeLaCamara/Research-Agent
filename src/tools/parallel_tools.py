# src/tools/parallel_tools.py

import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..state import AgentState

logger = logging.getLogger(__name__)

PARALLEL_STATUS_FILE = "/tmp/parallel_search_status.json"


def _write_status(done: list, running: list, total: int):
    try:
        data = {"done": done, "running": running, "total": total}
        tmp = PARALLEL_STATUS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, PARALLEL_STATUS_FILE)
    except Exception:
        pass


def _youtube_combined_node(state: AgentState) -> dict:
    """Run YouTube search + summarize sequentially (summarize depends on search)."""
    from .youtube_tools import search_videos_node, summarize_videos_node

    search_result = search_videos_node(state)
    merged_state = {**state, **search_result}
    summarize_result = summarize_videos_node(merged_state)
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

    # Enforce user RAG preference: if the checkbox is off, strip local_rag
    # from the plan even if a prior node slipped it in.
    if not state.get("use_rag", False) and "local_rag" in plan:
        plan = [s for s in plan if s != "local_rag"]
        logger.warning("parallel_search: dropped local_rag (use_rag=False)")

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
    done_sources = []

    _write_status(done=[], running=list(plan), total=len(plan))

    with ThreadPoolExecutor(max_workers=len(plan) or 1) as executor:
        for source_name in plan:
            fn = source_functions.get(source_name)
            if fn:
                future = executor.submit(fn, state)
                futures_map[future] = source_name
            else:
                logger.warning(f"Unknown source in plan: {source_name}")

        from concurrent.futures import TimeoutError as FutureTimeoutError
        try:
            for future in as_completed(futures_map, timeout=60):
                source_name = futures_map[future]
                try:
                    result = future.result()
                    combined.update(result)
                    logger.info(f"Source '{source_name}' completed successfully")
                except Exception as e:
                    logger.error(f"Source '{source_name}' failed: {e}")
                finally:
                    done_sources.append(source_name)
                    running = [s for s in plan if s not in done_sources]
                    _write_status(done=done_sources, running=running, total=len(plan))
        except FutureTimeoutError:
            for future, source_name in futures_map.items():
                if not future.done():
                    logger.warning(f"Source '{source_name}' timed out after 60s, skipping")

    # Cleanup status file
    try:
        os.remove(PARALLEL_STATUS_FILE)
    except Exception:
        pass

    combined["next_node"] = "END"
    logger.info(f"Parallel search completed. Keys: {list(combined.keys())}")
    return combined
