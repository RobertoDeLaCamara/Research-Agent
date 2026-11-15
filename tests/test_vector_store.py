import hashlib
import re

import numpy as np
import pytest
from chromadb import EmbeddingFunction

from src.tools.vector_store import VectorStoreManager, build_fts_query, looks_like_junk, rrf_fuse


class HashEmbedding(EmbeddingFunction):
    """Deterministic bag-of-words embedding: texts sharing words are close. No model download."""

    def __init__(self):
        pass

    def __call__(self, input):
        out = []
        for text in input:
            v = np.zeros(64, dtype=np.float32)
            for w in re.findall(r"[a-z0-9]+", text.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1.0
            n = np.linalg.norm(v)
            out.append((v / n if n else v).tolist())
        return out

    @staticmethod
    def name():
        return "hash-embedding-test"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return HashEmbedding()


@pytest.fixture
def store(tmp_path):
    return VectorStoreManager(str(tmp_path / "chroma"), embedding_function=HashEmbedding())


def doc(i, text, source="kb/a.pdf", page=1):
    return {"id": i, "text": text, "metadata": {"source": source, "filename": source.split("/")[-1], "page": page}}


# --- build_fts_query -------------------------------------------------------------------------

def test_fts_query_drops_stopwords_dedupes_and_quotes():
    assert build_fts_query("How does the Transformer attention work? attention!") == '"transformer" OR "attention" OR "work"'


@pytest.mark.parametrize("text", ['AND OR NOT', 'NEAR(a b)', '"unbalanced', "a-b:c*", "", None, "   ", "a"])
def test_fts_query_is_always_valid_match_syntax(text, store):
    store.add_documents([doc("x", "something about attention and transformers")])
    q = build_fts_query(text)
    assert q == "" or all(t.startswith('"') and t.endswith('"') for t in q.split(" OR "))
    store.query_lexical(text or "")  # must not raise


def test_fts_query_caps_term_count():
    assert len(build_fts_query(" ".join(f"word{i}" for i in range(100))).split(" OR ")) == 32


# --- rrf_fuse --------------------------------------------------------------------------------

def test_rrf_prefers_documents_found_by_both_rankings():
    scores = rrf_fuse([["a", "b", "c"], ["c", "d"]])
    assert max(scores, key=scores.get) == "c"
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert set(scores) == {"a", "b", "c", "d"}


def test_rrf_empty():
    assert rrf_fuse([[], []]) == {}


# --- lexical index follows writes ------------------------------------------------------------

def test_add_documents_populates_both_indexes(store):
    store.add_documents([doc("1", "gradient descent optimizes loss"), doc("2", "bayesian inference priors")])
    assert store.count() == 2 and store.lexical_count() == 2


def test_upsert_same_id_replaces_text_in_lexical_index(store):
    store.add_documents([doc("1", "alpha beta")])
    store.add_documents([doc("1", "gamma delta")])
    assert store.lexical_count() == 1
    assert store.query_lexical("alpha") == []
    assert [h["id"] for h in store.query_lexical("gamma")] == ["1"]


def test_delete_documents_removes_from_both(store):
    store.add_documents([doc("1", "alpha"), doc("2", "alpha beta")])
    store.delete_documents(["1"])
    assert store.count() == 1 and store.lexical_count() == 1
    assert [h["id"] for h in store.query_lexical("alpha")] == ["2"]


def test_delete_by_source_removes_only_that_file(store):
    store.add_documents([doc("1", "alpha", source="kb/a.pdf"), doc("2", "alpha", source="kb/b.pdf")])
    store.delete_by_source("kb/a.pdf")
    assert store.indexed_sources() == {"kb/b.pdf"}
    assert store.count() == 1


def test_lexical_backfill_from_existing_chroma_collection(tmp_path):
    chroma = str(tmp_path / "chroma")
    old = VectorStoreManager(chroma, embedding_function=HashEmbedding(), lexical_path=str(tmp_path / "old.db"))
    old.add_documents([doc("1", "alpha beta"), doc("2", "gamma")])
    # a new store over the same Chroma dir but with no lexical db yet (the situation on first deploy)
    fresh = VectorStoreManager(chroma, embedding_function=HashEmbedding(), lexical_path=str(tmp_path / "fresh.db"))
    assert fresh.lexical_count() == 0
    hits = fresh.query_lexical("gamma")
    assert [h["id"] for h in hits] == ["2"] and fresh.lexical_count() == 2


def test_lexical_index_rebuilt_when_out_of_sync(store):
    store.add_documents([doc("1", "alpha"), doc("2", "beta")])
    store._lexical_upsert([("ghost", "kb/z.pdf", 1, "phantom text")])  # drift: extra row
    store._lexical_ready = False
    store.ensure_lexical_index()
    assert store.lexical_count() == 2 and store.query_lexical("phantom") == []


# --- retrieval -------------------------------------------------------------------------------

def test_lexical_returns_metadata_with_page(store):
    store.add_documents([doc("1", "backpropagation computes gradients", source="kb/ml/book.pdf", page=42)])
    [hit] = store.query_lexical("backpropagation")
    assert hit["metadata"] == {"source": "kb/ml/book.pdf", "filename": "book.pdf", "page": 42}


def test_lexical_ranks_rarer_term_matches_first(store):
    # "learning" is in two of three chunks (low IDF), "hessian" in one (high IDF)
    store.add_documents([
        doc("common1", "learning learning is common in many books"),
        doc("common2", "learning rates matter a lot"),
        doc("rare", "the hessian eigenvalue spectrum of the loss"),
    ])
    assert store.query_lexical("hessian learning", n_results=3)[0]["id"] == "rare"


def test_hybrid_combines_hits_found_by_only_one_retriever(store):
    store.add_documents([
        doc("kw", "xylophone zebra quartz"),                    # shares a rare word with the query
        doc("sem1", "neural networks learn representations"),   # shares no rare word, near in vector space
        doc("other", "cooking pasta with tomato sauce"),
    ])
    hits = store.query_hybrid("quartz neural networks representations", n_results=3)
    ids = [h["id"] for h in hits]
    assert "kw" in ids and "sem1" in ids
    assert all({"score", "found_by", "content", "metadata"} <= set(h) for h in hits)


def test_hybrid_ranks_doc_found_by_both_retrievers_first(store):
    store.add_documents([
        doc("both", "attention mechanism transformer model"),
        doc("lex_only", "attention economics and marketing budgets"),
        doc("noise", "volcano geology magma"),
    ])
    hits = store.query_hybrid("transformer attention mechanism", n_results=3)
    assert hits[0]["id"] == "both" and sorted(hits[0]["found_by"]) == ["dense", "lexical"]


def test_hybrid_on_empty_store_and_empty_query(store):
    assert store.query_hybrid("anything") == []
    store.add_documents([doc("1", "alpha")])
    assert store.query_lexical("the of and") == []  # only stopwords
    assert store.query_hybrid("")[0]["id"] == "1" or store.query_hybrid("") == []


def test_hybrid_survives_lexical_failure(store, monkeypatch):
    store.add_documents([doc("1", "alpha beta")])
    monkeypatch.setattr(store, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("db locked")))
    hits = store.query_hybrid("alpha beta", n_results=1)  # falls back to dense only
    assert [h["id"] for h in hits] == ["1"] and hits[0]["found_by"] == ["dense"]


# --- looks_like_junk ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Chapter 13: Creating a Cluster " + "." * 50 + " 373",
    "A . . . . . . . . . . . . 12",
    "\ufffd" * 40 + " 471\nReferences " + "\ufffd" * 40,
    "12345 67890 " * 30,      # long, no real words
    "establisheddeep" * 30,   # long, no spaces (bad extraction)
    "   \n ",
    "[Page 4]\n5G NR: The Next\nGeneration Wireless\nAccess Technology\nErik Dahlman\nStefan Parkvall\nJohan Sko¨ld",
    "L.A. Amaral\ne-mail: leonardo.amaral@acad.pucrs.br\nE. de Matos\ne-mail: everton.matos.001@acad.pucrs.br\n© Springer 2016",
    "2012 Int. Conf. (CTS), pp. 21-26 (2012). doi:10.1109/CTS.2012.6261022\n9. Chen, S.: IEEE Commun. Mag. (2014). doi:10.1109/MCOM.2014.6815891",
])
def test_looks_like_junk_true(text):
    assert looks_like_junk(text)


@pytest.mark.parametrize("text", [
    "The scheduler monitors the API for unscheduled pods and schedules them onto nodes " * 4,
    "for (i = 0; i < n; i++) { total += a[i]; }",  # code listing: few words but real content
    "attention is all you need",                   # short but legitimate
    "12 34 56 78 90",                              # short: too little to judge
    "The ellipsis... appears only once in this otherwise normal sentence about gradient descent " * 3,
])
def test_looks_like_junk_false(text):
    assert not looks_like_junk(text)
