import os
from unittest.mock import patch

from src.tools.rag_tools import local_rag_node, _hybrid_local_research


class FakeStore:
    def __init__(self, count=3, hits=None, boom=False):
        self._count, self._hits, self._boom = count, hits or [], boom
        self.calls = []

    def count(self):
        return self._count

    def query_hybrid(self, query, n_results=5, candidates=50):
        self.calls.append((query, n_results))
        if self._boom:
            raise RuntimeError("chroma down")
        return self._hits


HIT = {"id": "kb/book.pdf_3", "content": "attention is all you need", "score": 0.0325,
       "metadata": {"source": "./knowledge_base/ml/book.pdf", "filename": "book.pdf", "page": 7}}


def run(state, store, env=None):
    with patch.dict(os.environ, env or {"RAG_MODE": "hybrid"}), \
         patch("src.tools.vector_store.get_default_store", return_value=store):
        return local_rag_node(state)


def test_hybrid_mode_returns_chunks_in_local_research_shape(mock_agent_state):
    store = FakeStore(hits=[HIT])
    out = run(mock_agent_state, store)
    [item] = out["local_research"]
    assert item["title"] == "book.pdf (p. 7)" and item["content"] == "attention is all you need"
    assert item["url"].startswith("file://") and item["url"].endswith("/knowledge_base/ml/book.pdf#page=7")
    assert item["score"] == 0.0325
    assert out["source_metadata"]["local_rag"]["reliability"] == 5
    assert store.calls == [("Test Topic", 24)]  # 3 x RAG_TOP_K, junk is filtered afterwards


def test_hybrid_mode_respects_top_k_and_omits_page_for_text_files(mock_agent_state):
    hit = dict(HIT, metadata={"source": "./kb/notes.txt", "filename": "notes.txt"})
    store = FakeStore(hits=[hit])
    out = run(mock_agent_state, store, {"RAG_MODE": "Hybrid", "RAG_TOP_K": "3"})
    assert store.calls[0][1] == 9
    assert out["local_research"][0]["title"] == "notes.txt" and "#page" not in out["local_research"][0]["url"]


def test_hybrid_mode_empty_topic_returns_nothing(mock_agent_state):
    mock_agent_state["topic"] = "  "
    assert run(mock_agent_state, FakeStore(hits=[HIT]))["local_research"] == []


def test_hybrid_unavailable_or_empty_index_returns_none_for_fallback():
    with patch("src.tools.vector_store.get_default_store", return_value=FakeStore(count=0)):
        assert _hybrid_local_research("x") is None
    with patch("src.tools.vector_store.get_default_store", return_value=FakeStore(boom=True)):
        assert _hybrid_local_research("x") is None
    with patch("src.tools.vector_store.get_default_store", side_effect=RuntimeError("no chroma")):
        assert _hybrid_local_research("x") is None


def test_hybrid_failure_falls_back_to_legacy_file_scan(mock_agent_state, tmp_path):
    (tmp_path / "doc.txt").write_text("transformers use attention")
    mock_agent_state["topic"] = "attention"
    out = run(mock_agent_state, FakeStore(boom=True), {"RAG_MODE": "hybrid", "RAG_KB_DIR": str(tmp_path)})
    assert [r["title"] for r in out["local_research"]] == ["doc.txt"]  # legacy shape: whole file


def test_default_mode_never_touches_the_vector_store(mock_agent_state, tmp_path):
    (tmp_path / "doc.txt").write_text("attention")
    mock_agent_state["topic"] = "attention"
    store = FakeStore(hits=[HIT])
    out = run(mock_agent_state, store, {"RAG_KB_DIR": str(tmp_path), "RAG_MODE": "legacy"})
    assert store.calls == [] and out["local_research"][0]["title"] == "doc.txt"


def test_hybrid_mode_drops_junk_chunks_and_overfetches(mock_agent_state):
    toc = dict(HIT, id="toc", content="Chapter 13: Creating Pods " + "." * 60 + " 373")
    store = FakeStore(hits=[toc, HIT])
    out = run(mock_agent_state, store, {"RAG_MODE": "hybrid", "RAG_TOP_K": "1"})
    assert [r["content"] for r in out["local_research"]] == ["attention is all you need"]
    assert store.calls[0][1] == 3  # asked for 3x top_k so filtering still leaves enough
