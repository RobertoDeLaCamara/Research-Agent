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


def test_books_rag_url_returns_formatted_book_chunks(mock_agent_state, monkeypatch, tmp_path):
    monkeypatch.setenv("RAG_KB_DIR", str(tmp_path))  # empty knowledge base: only the book chunk comes back
    monkeypatch.setenv("BOOKS_RAG_URL", "http://host.docker.internal:8765")
    monkeypatch.setenv("RAG_TOP_K", "2")
    fake_resp = type("Resp", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {
            "results": [
                {
                    "book_title": "Deep Learning with Python",
                    "file_name": "dl_python.pdf",
                    "file_path": "C:/Books/dl_python.pdf",
                    "page_start": 42,
                    "page_end": 44,
                    "chapter": "Chapter 3",
                    "text": "Hopfield networks minimize an energy function to converge to attractors.",
                    "similarity_score": 0.8123,
                }
            ]
        },
    })()
    with patch("requests.get", return_value=fake_resp) as mock_get:
        out = local_rag_node(mock_agent_state)
    assert len(out["local_research"]) == 1
    item = out["local_research"][0]
    assert item["title"] == "Deep Learning with Python (pp. 42-44, Chapter 3)"
    assert item["content"].startswith("Hopfield networks")
    assert item["url"] == "file://C:/Books/dl_python.pdf#page=42"
    assert item["score"] == 0.8123
    assert mock_get.called


BOOK_HIT = {"book_title": "Book A", "file_path": "/b/a.pdf", "page_start": 3, "page_end": 3,
            "chapter": "Intro", "text": "Hopfield energy converges to stable attractors.", "similarity_score": 0.7}


def _books_resp(hits):
    return type("Resp", (), {"raise_for_status": lambda self: None, "json": lambda self: {"results": hits}})()


def test_books_and_knowledge_base_results_are_combined(mock_agent_state):
    store = FakeStore(hits=[HIT])
    env = {"RAG_MODE": "hybrid", "BOOKS_RAG_URL": "http://127.0.0.1:8765"}
    with patch("requests.get", return_value=_books_resp([BOOK_HIT])):
        out = run(mock_agent_state, store, env)
    assert [r["title"] for r in out["local_research"]] == ["Book A (p. 3, Intro)", "book.pdf (p. 7)"]


def test_unreachable_books_service_falls_back_to_knowledge_base(mock_agent_state):
    import requests
    store = FakeStore(hits=[HIT])
    env = {"RAG_MODE": "hybrid", "BOOKS_RAG_URL": "http://host.docker.internal:8765"}
    with patch("requests.get", side_effect=requests.ConnectionError("down")) as mock_get:
        out = run(mock_agent_state, store, env)
    assert [r["title"] for r in out["local_research"]] == ["book.pdf (p. 7)"]
    # tried the configured host, then the swapped one
    assert [c.args[0] for c in mock_get.call_args_list] == [
        "http://host.docker.internal:8765/api/search", "http://127.0.0.1:8765/api/search"]


def test_books_rag_filters_preface_references_and_offtopic_economics_books(mock_agent_state, monkeypatch, tmp_path):
    """Regression test: BOOKS_RAG_URL must drop Preface/References chapters, author email blocks,
    title pages, and off-topic Economics books that lack the query's technical anchors (6G/3GPP/agentic)."""
    monkeypatch.setenv("RAG_KB_DIR", str(tmp_path))
    monkeypatch.setenv("BOOKS_RAG_URL", "http://127.0.0.1:8765")
    mock_agent_state["topic"] = "IA agentica en redes 6G: estado del arte, evolución y estandarización en 3gpp"
    mock_agent_state["queries"] = {"en": "Agentic AI in 6G networks and 3GPP standardization"}

    hits = [
        {
            "book_title": "Cellular Communication Networks and Standards",
            "file_path": "/books/cellular_6g.pdf",
            "page_start": 6,
            "page_end": 7,
            "chapter": "Preface",
            "text": "This textbook offers students a review of cellular systems up to 6G.",
            "similarity_score": 0.81,
        },
        {
            "book_title": "EconomÃ­a, teorÃ­a y polÃ­tica",
            "file_path": "/books/economia.pdf",
            "page_start": 252,
            "page_end": 253,
            "chapter": "11.4. Los bienes públicos",
            "text": "Los avances en las tecnologías de la información han facilitado la aparición de externalidades positivas.",
            "similarity_score": 0.79,
        },
        {
            "book_title": "Net Of Things In 5G Mobile Technologies",
            "file_path": "/books/iot_5g.pdf",
            "page_start": 412,
            "page_end": 413,
            "chapter": "References",
            "text": "Chen, S.: The requirements for 5G. IEEE Commun. Mag. (2014).",
            "similarity_score": 0.78,
        },
        {
            "book_title": "Cellular Communication Networks and Standards",
            "file_path": "/books/cellular_6g.pdf",
            "page_start": 32,
            "page_end": 32,
            "chapter": "1.4 Summary",
            "text": "We elaborate on ongoing research and development efforts toward the first 6G standard in 3GPP.",
            "similarity_score": 0.79,
        },
    ]
    with patch("requests.get", return_value=_books_resp(hits)):
        out = local_rag_node(mock_agent_state)

    assert [r["title"] for r in out["local_research"]] == [
        "Cellular Communication Networks and Standards (p. 32, 1.4 Summary)"
    ]
