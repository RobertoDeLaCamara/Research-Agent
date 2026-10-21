import os

import pytest

from src.tools.rag_index import chunk_text, file_chunks, ingest_directory, main
from src.tools.vector_store import VectorStoreManager
from tests.test_vector_store import HashEmbedding


@pytest.fixture
def store(tmp_path):
    return VectorStoreManager(str(tmp_path / "chroma"), embedding_function=HashEmbedding())


@pytest.fixture
def kb(tmp_path):
    root = tmp_path / "kb"
    (root / "sub").mkdir(parents=True)
    (root / "notes.txt").write_text("gradient descent updates weights. " * 80)
    (root / "sub" / "bayes.txt").write_text("posterior is proportional to likelihood times prior. " * 40)
    (root / "ignored.docx").write_text("not indexed")
    return str(root)


# --- chunking ---------------------------------------------------------------------------------

def test_chunk_text_sliding_window_with_overlap():
    text = "".join(chr(65 + i % 26) for i in range(2500))
    chunks = chunk_text(text, size=1000, overlap=100)
    assert [len(c) for c in chunks] == [1000, 1000, 700]
    assert chunks[0][-100:] == chunks[1][:100]
    assert chunks[1][-100:] == chunks[2][:100]


def test_chunk_text_edge_cases():
    assert chunk_text("") == [] and chunk_text("   \n  ") == []
    assert chunk_text("short") == ["short"]
    assert chunk_text("x" * 1000) == ["x" * 1000]  # exactly one window, no empty trailing chunk


# --- file_chunks ------------------------------------------------------------------------------

def test_file_chunks_ids_and_metadata_for_text_file(kb):
    path = os.path.join(kb, "notes.txt")
    docs = list(file_chunks(path, source=path))
    assert docs and [d["id"] for d in docs] == [f"{path}_{i}" for i in range(len(docs))]
    assert docs[0]["metadata"] == {"source": path, "filename": "notes.txt"}  # no page key (Chroma rejects None)


def test_file_chunks_pdf_records_page_numbers(tmp_path, monkeypatch):
    class Page:
        def __init__(self, t): self.t = t
        def extract_text(self): return self.t

    class Reader:
        is_encrypted = False

        def __init__(self, f): self.pages = [Page("alpha " * 300), Page(""), Page("omega " * 50)]

    monkeypatch.setattr("src.tools.rag_index.pypdf.PdfReader", Reader)
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-fake")
    docs = list(file_chunks(str(pdf), source="kb/book.pdf"))
    assert {d["metadata"]["page"] for d in docs} == {1, 3}  # blank page 2 yields nothing
    assert [d["id"] for d in docs] == [f"kb/book.pdf_{i}" for i in range(len(docs))]
    capped = list(file_chunks(str(pdf), source="kb/book.pdf", max_pages=1))
    assert {d["metadata"]["page"] for d in capped} == {1}


# --- ingest_directory -------------------------------------------------------------------------

def test_ingest_indexes_supported_files_only(kb, store):
    stats = ingest_directory(kb, store)
    assert stats["files"] == 2 and stats["indexed"] == 2 and stats["failed"] == 0
    assert stats["chunks"] == store.count() == store.lexical_count()
    assert {os.path.basename(s) for s in store.indexed_sources()} == {"notes.txt", "bayes.txt"}


def test_ingest_is_incremental_and_replaces_changed_files(kb, store):
    ingest_directory(kb, store)
    before = store.count()
    again = ingest_directory(kb, store)
    assert again["indexed"] == 0 and again["skipped"] == 2 and store.count() == before

    path = os.path.join(kb, "notes.txt")
    open(path, "w").write("completely different content about volcano geology")
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + 10))
    changed = ingest_directory(kb, store)
    assert changed["indexed"] == 1
    assert store.query_lexical("volcano")[0]["metadata"]["filename"] == "notes.txt"
    assert store.query_lexical("gradient", n_results=20) == []  # old chunks of that file are gone, no duplicates


def test_ingest_only_missing_skips_sources_already_in_store(kb, store):
    first = os.path.join(kb, "notes.txt")
    store.add_documents([{"id": f"{first}_0", "text": "legacy chunk", "metadata": {"source": first}}])
    stats = ingest_directory(kb, store, only_missing=True)
    assert stats["indexed"] == 1 and stats["skipped"] == 1
    assert store.query_lexical("legacy")  # untouched


def test_ingest_limit_and_failures_do_not_abort(kb, store, monkeypatch):
    assert ingest_directory(kb, store, limit=1)["indexed"] == 1

    import src.tools.rag_index as ri
    real = ri.file_chunks
    monkeypatch.setattr(ri, "file_chunks", lambda p, s, m=None: (_ for _ in ()).throw(OSError("corrupt")) if "bayes" in p else real(p, s, m))
    stats = ingest_directory(kb, store)
    # notes.txt was indexed by the limited run above, so only the corrupt file is attempted
    assert stats["failed"] == 1 and stats["indexed"] == 0 and stats["skipped"] == 1


def test_cli_main_reports_and_returns_exit_code(kb, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.tools.rag_index.VectorStoreManager", lambda d: VectorStoreManager(d, embedding_function=HashEmbedding()))
    rc = main(["--kb", kb, "--persist-dir", str(tmp_path / "cli_chroma")])
    assert rc == 0 and "'indexed': 2" in capsys.readouterr().out


def test_pdf_with_empty_user_password_is_decrypted_before_reading(tmp_path, monkeypatch):
    calls = []

    class Page:
        def extract_text(self): return "secret sauce " * 20

    class Reader:
        is_encrypted = True
        pages = [Page()]
        def __init__(self, f): pass
        def decrypt(self, pw):
            calls.append(pw)
            return 1

    monkeypatch.setattr("src.tools.rag_index.pypdf.PdfReader", Reader)
    pdf = tmp_path / "locked.pdf"
    pdf.write_bytes(b"%PDF-fake")
    assert list(file_chunks(str(pdf), "kb/locked.pdf")) and calls == [""]


def test_junk_chunks_are_not_indexed(tmp_path):
    toc = "Chapter 1: Getting Started " + "." * 60 + " 3\nChapter 2: Pods " + "." * 60 + " 17\n"
    body = "The scheduler watches the API server for pods that have no node assigned and picks one. " * 20
    path = tmp_path / "book.txt"
    path.write_text(toc + "\n" + body)
    texts = [d["text"] for d in file_chunks(str(path), "kb/book.txt")]
    assert texts and not any("......" in t for t in texts[1:])
    assert any("scheduler" in t for t in texts)
