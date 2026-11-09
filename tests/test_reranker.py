import os
from unittest.mock import patch, MagicMock

import requests

from src.tools.reranker import rerank_hits, rerank_scores
from src.tools.rag_tools import _hybrid_local_research

URL = {"RERANK_URL": "http://host.docker.internal:8099/rerank"}


def hit(i, text="x"):
    return {"id": str(i), "content": f"{text}{i}", "score": 1 / (i + 1), "metadata": {"source": "./kb/b.pdf", "filename": "b.pdf", "page": i}}


def ok_response(scores):
    r = MagicMock()
    r.json.return_value = {"scores": scores}
    r.raise_for_status.return_value = None
    return r


def test_disabled_without_url_and_makes_no_request():
    with patch.dict(os.environ, {"RERANK_URL": ""}), patch("src.tools.reranker.requests.post") as post:
        assert rerank_scores("q", ["a"]) is None
        assert rerank_hits("q", [hit(0)]) == [hit(0)]
    post.assert_not_called()


def test_reorders_by_score_and_is_stable_on_ties():
    hits = [hit(0), hit(1), hit(2), hit(3)]
    with patch.dict(os.environ, URL), patch("src.tools.reranker.requests.post", return_value=ok_response([0.1, 0.9, 0.9, -2.0])):
        out = rerank_hits("q", hits)
    assert [h["id"] for h in out] == ["1", "2", "0", "3"]
    assert out[0]["rerank_score"] == 0.9 and "rerank_score" not in hits[0]


def test_failures_keep_original_order():
    hits = [hit(0), hit(1)]
    bad_len = ok_response([0.5])  # wrong number of scores
    for effect in (requests.ConnectionError("down"), requests.Timeout("slow")):
        with patch.dict(os.environ, URL), patch("src.tools.reranker.requests.post", side_effect=effect):
            assert rerank_hits("q", hits) == hits
    with patch.dict(os.environ, URL), patch("src.tools.reranker.requests.post", return_value=bad_len):
        assert rerank_hits("q", hits) == hits
    http_err = ok_response([1, 2]); http_err.raise_for_status.side_effect = requests.HTTPError("500")
    with patch.dict(os.environ, URL), patch("src.tools.reranker.requests.post", return_value=http_err):
        assert rerank_hits("q", hits) == hits


def test_documents_are_truncated_before_sending():
    with patch.dict(os.environ, URL), patch("src.tools.reranker.requests.post", return_value=ok_response([1.0])) as post:
        rerank_scores("q", ["y" * 10_000])
    assert len(post.call_args.kwargs["json"]["documents"][0]) == 2000


class FakeStore:
    def __init__(self, hits): self._hits, self.calls = hits, []
    def count(self): return len(self._hits)
    def query_hybrid(self, query, n_results=5, candidates=50):
        self.calls.append(n_results); return self._hits[:n_results]


def run(store, env, scores=None):
    with patch.dict(os.environ, env), patch("src.tools.vector_store.get_default_store", return_value=store), \
         patch("src.tools.reranker.requests.post", return_value=ok_response(scores)) as post:
        return _hybrid_local_research("topic"), post


def test_rag_default_path_unchanged_without_rerank_url():
    store = FakeStore([hit(i, "word ") for i in range(40)])
    out, post = run(store, {"RERANK_URL": "", "RAG_TOP_K": "5"})
    assert store.calls == [15] and len(out) == 5 and out[0]["title"] == "b.pdf"
    post.assert_not_called()


def test_rag_with_rerank_fetches_pool_and_returns_best_top_k():
    store = FakeStore([hit(i, "word ") for i in range(40)])
    scores = [float(i) for i in range(30)]  # last candidate is best
    out, post = run(store, {**URL, "RAG_TOP_K": "3"}, scores)
    assert store.calls == [30]
    assert [r["title"] for r in out] == ["b.pdf (p. 29)", "b.pdf (p. 28)", "b.pdf (p. 27)"]
