"""Index the knowledge base into the hybrid store (ChromaDB + SQLite FTS5).

    python -m src.tools.rag_index                      # new or changed files under $RAG_KB_DIR
    python -m src.tools.rag_index --only-missing       # skip files that already have chunks
    python -m src.tools.rag_index --max-pages 300      # cap pages per PDF (default: all pages)

Junk chunks (table-of-contents dot leaders, broken characters) are skipped. Chunks are 1000 characters with a 100 character overlap, with id ``<source>_<n>``: the same scheme
the original semantic index used, so existing collections keep working and re-indexing a file
replaces its chunks instead of duplicating them.
"""
import argparse
import logging
import os
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import pypdf

from .vector_store import VectorStoreManager, get_default_store, looks_like_junk

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
OVERLAP = 100
BATCH_SIZE = 128
SUPPORTED = (".pdf", ".txt")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    """Sliding window over ``text``; blank windows are dropped."""
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append(piece)
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


def read_pages(path: str, max_pages: Optional[int] = None) -> Iterator[Tuple[Optional[int], str]]:
    """Yield (page_number, text). Text files are a single page-less block (page None)."""
    if path.lower().endswith(".pdf"):
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            if reader.is_encrypted:  # many publisher PDFs are "encrypted" with an empty user password
                reader.decrypt("")
            for n, page in enumerate(reader.pages, start=1):
                if max_pages and n > max_pages:
                    break
                try:
                    text = page.extract_text() or ""
                except Exception as e:  # one unreadable page must not lose the book
                    logger.warning(f"{os.path.basename(path)} p.{n}: {e}")
                    continue
                yield n, text
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            yield None, f.read()


def file_chunks(path: str, source: str, max_pages: Optional[int] = None) -> Iterator[Dict]:
    """All chunks of one file as documents ready for ``VectorStoreManager.add_documents``."""
    n = 0
    for page, text in read_pages(path, max_pages):
        for piece in chunk_text(text):
            if looks_like_junk(piece):
                continue
            meta: Dict[str, object] = {"source": source, "filename": os.path.basename(path)}
            if page is not None:  # Chroma rejects None metadata values
                meta["page"] = page
            yield {"id": f"{source}_{n}", "text": piece, "metadata": meta}
            n += 1


def file_signature(path: str, max_pages: Optional[int]) -> str:
    st = os.stat(path)
    return f"{st.st_mtime}_{st.st_size}_{max_pages or 'all'}"


def ingest_directory(
    kb_dir: str,
    store: Optional[VectorStoreManager] = None,
    max_pages: Optional[int] = None,
    only_missing: bool = False,
    limit: Optional[int] = None,
    batch_size: int = BATCH_SIZE,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, int]:
    """Index every .pdf/.txt under ``kb_dir`` that is new or changed. Never raises per file."""
    store = store or get_default_store()
    files = sorted(
        os.path.join(root, name)
        for root, _, names in os.walk(kb_dir)
        for name in names
        if name.lower().endswith(SUPPORTED)
    )
    known = store.indexed_sources() if only_missing else set()
    stats = {"files": len(files), "indexed": 0, "skipped": 0, "failed": 0, "chunks": 0}
    done = 0
    for i, path in enumerate(files, start=1):
        if progress:
            progress(i, len(files), os.path.basename(path))
        source = path  # as walked from kb_dir, e.g. ./knowledge_base/sub/book.pdf
        try:
            sig = file_signature(path, max_pages)
            if (only_missing and source in known) or (not only_missing and store.get_file_signature(source) == sig):
                stats["skipped"] += 1
                continue
            if limit is not None and done >= limit:
                break
            store.delete_by_source(source)  # replace, never duplicate
            batch, total = [], 0
            for doc in file_chunks(path, source, max_pages):
                batch.append(doc)
                if len(batch) >= batch_size:
                    store.add_documents(batch)
                    total += len(batch)
                    batch = []
            if batch:
                store.add_documents(batch)
                total += len(batch)
            store.set_file_signature(source, sig, total)
            stats["indexed"] += 1
            stats["chunks"] += total
            done += 1
            logger.info(f"indexed {os.path.basename(path)}: {total} chunks")
        except Exception as e:
            stats["failed"] += 1
            logger.error(f"failed to index {path}: {e}")
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=os.getenv("RAG_KB_DIR", "./knowledge_base"))
    ap.add_argument("--max-pages", type=int, default=int(os.getenv("RAG_INDEX_MAX_PAGES", "0")) or None)
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="index at most N files this run")
    ap.add_argument("--persist-dir", default=None, help="default: $CHROMA_PERSIST_DIR or /app/data/chroma_db")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = VectorStoreManager(args.persist_dir) if args.persist_dir else get_default_store()
    store.ensure_lexical_index()  # build the keyword index now rather than on the first agent query
    stats = ingest_directory(args.kb, store, args.max_pages, args.only_missing, args.limit)
    print(stats)
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
