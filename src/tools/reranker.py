"""Optional cross-encoder reranking for the hybrid RAG index.

The reranker runs as a separate HTTP service (``scripts/rerank_server.py``, GPU on the host) so the
agent container needs neither torch nor a GPU. Opt-in: set ``RERANK_URL``. On any failure the caller
keeps the original (RRF) order, so the feature can never make retrieval worse than it is today.
"""
import os
import logging
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
MAX_CHARS = 2000  # the cross-encoder truncates at 512 tokens anyway; do not ship more over the wire


def rerank_url() -> Optional[str]:
    return (os.getenv("RERANK_URL") or "").strip() or None


def rerank_scores(query: str, documents: List[str]) -> Optional[List[float]]:
    """Relevance score per document (higher is better), or None when reranking is off or failed."""
    url = rerank_url()
    if not url or not documents:
        return None
    try:
        timeout = float(os.getenv("RERANK_TIMEOUT", DEFAULT_TIMEOUT))
        resp = requests.post(
            url, json={"query": query, "documents": [d[:MAX_CHARS] for d in documents]}, timeout=timeout
        )
        resp.raise_for_status()
        scores = resp.json()["scores"]
        if len(scores) != len(documents):
            raise ValueError(f"got {len(scores)} scores for {len(documents)} documents")
        return [float(s) for s in scores]
    except Exception as e:  # network, HTTP, JSON or shape errors: all mean "keep the RRF order"
        logger.warning(f"rerank_failed_keeping_rrf_order: {e}")
        return None


def rerank_hits(query: str, hits: List[dict]) -> List[dict]:
    """``hits`` reordered by cross-encoder score (each gets ``rerank_score``); unchanged on failure."""
    scores = rerank_scores(query, [h["content"] for h in hits])
    if scores is None:
        return hits
    ranked = sorted(zip(scores, range(len(hits))), key=lambda p: (-p[0], p[1]))
    return [dict(hits[i], rerank_score=round(s, 6)) for s, i in ranked]
