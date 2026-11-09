import os
import re
import sqlite3
import logging
import threading
from contextlib import contextmanager
from typing import List, Dict, Any, Mapping, Optional
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

DEFAULT_PERSIST_DIR = "/app/data/chroma_db"
RRF_K = 60  # Reciprocal Rank Fusion constant; 60 is the value from the original paper.

# Words that carry no retrieval signal. Same list used when the hybrid ranking was benchmarked.
STOPWORDS = frozenset(
    "a an the of and or to in on for with is are was were be been it this that these those "
    "as by at from how what which who why when does do did can could would should about into "
    "their its not than then so such".split()
)


_DOT_LEADERS = re.compile(r"\.{8,}|(\. ){8,}|(…\s*){4,}")
_CODE_HINT = re.compile(r"[;{}()=]")


def looks_like_junk(text: str) -> bool:
    """Chunks that match keywords but carry no content: table-of-contents dot leaders, text with
    broken characters (bad OCR/encoding), or a long run of text with almost no real words. Code
    listings and short legitimate chunks (last window of a page, small notes) are NOT junk."""
    if not text.strip():
        return True
    if _DOT_LEADERS.search(text):
        return True
    if text.count("\ufffd") / max(len(text), 1) > 0.03:
        return True
    return len(text) >= 200 and len(re.findall(r"\b[A-Za-z]{3,}\b", text)) < 25 and not _CODE_HINT.search(text)


def build_fts_query(text: str, max_terms: int = 32) -> str:
    """Turn free text into a safe FTS5 MATCH expression (quoted terms joined with OR).

    User text must never reach MATCH unescaped: ``AND``, ``NEAR``, quotes or ``-`` would be parsed as
    FTS5 syntax and raise ``sqlite3.OperationalError``. Returns "" when nothing is searchable.
    """
    seen = []
    for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(tok) > 1 and tok not in STOPWORDS and tok not in seen:
            seen.append(tok)
        if len(seen) >= max_terms:
            break
    return " OR ".join(f'"{t}"' for t in seen)


def rrf_fuse(rankings: List[List[str]], k: int = RRF_K) -> Dict[str, float]:
    """Reciprocal Rank Fusion: each ranking is a list of ids, best first."""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


class VectorStoreManager:
    """
    Manages the ChromaDB vector store for Semantic RAG, plus a SQLite FTS5 (BM25) index of the same
    chunks so that queries can be answered with hybrid retrieval (dense + keyword, fused with RRF).

    The lexical index lives in ``lexical_path`` (default: ``rag_lexical.db`` next to the Chroma
    directory) and is rebuilt automatically from Chroma when the two disagree on the chunk count.
    """

    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        embedding_function=None,
        lexical_path: Optional[str] = None,
    ):
        self.persist_directory = persist_directory
        self.lexical_path = lexical_path or os.path.join(
            os.path.dirname(persist_directory.rstrip("/")), "rag_lexical.db"
        )
        self._client = None
        self._collection = None
        self._lexical_ready = False
        self._lock = threading.Lock()

        # Ensure directory exists
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory, exist_ok=True)

        try:
            # Initialize Client
            self._client = chromadb.PersistentClient(path=persist_directory)

            # Default Embedding Function (all-MiniLM-L6-v2)
            # This downloads the model on first use (~80MB)
            self._embedding_fn = embedding_function or embedding_functions.DefaultEmbeddingFunction()

            # Get or Create Collection
            self._collection = self._client.get_or_create_collection(
                name="rag_knowledge_base",
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"} # Cosine similarity
            )
            logger.info(f"Vector Store initialized at {persist_directory}")

        except Exception as e:
            logger.error(f"Failed to initialize Vector Store: {e}")
            self._client = None

    # ------------------------------------------------------------------ lexical index

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.lexical_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                rowid INTEGER PRIMARY KEY,
                id TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL DEFAULT '',
                page INTEGER,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS indexed_files (
                source TEXT PRIMARY KEY,
                sig TEXT NOT NULL,
                chunks INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text, content='chunks', content_rowid='rowid', tokenize='unicode61'
            );
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
                INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
            END;
            """
        )
        return conn

    @contextmanager
    def _db(self):
        """One short-lived connection per operation: commit on success, always close."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _lexical_row(doc_id: str, text: str, metadata: Optional[Mapping[str, Any]]):
        meta = metadata or {}
        page = meta.get("page")
        return (doc_id, str(meta.get("source", "")), int(page) if isinstance(page, (int, float)) else None, text)

    def _lexical_upsert(self, rows: List[tuple]):
        if not rows:
            return
        with self._db() as conn:
            conn.executemany(
                "INSERT INTO chunks(id, source, page, text) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET source=excluded.source, page=excluded.page, text=excluded.text",
                rows,
            )

    def lexical_count(self) -> int:
        with self._db() as conn:
            return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def rebuild_lexical_from_chroma(self, batch_size: int = 2000) -> int:
        """Recreate the keyword index from what is stored in Chroma. Returns the number of chunks."""
        if not self._collection:
            return 0
        total = self._collection.count()
        with self._db() as conn:
            conn.execute("DELETE FROM chunks")
        done = 0
        for offset in range(0, total, batch_size):
            res = self._collection.get(limit=batch_size, offset=offset, include=["documents", "metadatas"])
            rows = [
                self._lexical_row(i, d, m)
                for i, d, m in zip(res["ids"], res["documents"] or [], res["metadatas"] or [])
                if d
            ]
            self._lexical_upsert(rows)
            done += len(rows)
        logger.info(f"Lexical index rebuilt from Chroma: {done} chunks")
        return done

    def ensure_lexical_index(self):
        """Backfill the keyword index when it is missing or out of sync (checked once per process)."""
        if self._lexical_ready or not self._collection:
            return
        with self._lock:
            if self._lexical_ready:
                return
            if self.lexical_count() != self._collection.count():
                self.rebuild_lexical_from_chroma()
            self._lexical_ready = True

    # ------------------------------------------------------------------ write path

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds documents to the vector store.
        Args:
            documents: List of dicts with keys: 'id', 'text', 'metadata'
        """
        if not self._collection or not documents:
            return

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        try:
            # Chroma handles batching, but we can do small batches if needed.
            # For now, pass all.
            self._collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Upserted {len(documents)} docs to Vector Store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return

        try:
            self._lexical_upsert([self._lexical_row(i, t, m) for i, t, m in zip(ids, texts, metadatas)])
        except Exception as e:
            # Not fatal: the next ensure_lexical_index() sees the count mismatch and rebuilds.
            self._lexical_ready = False
            logger.error(f"Failed to update lexical index: {e}")

    def delete_documents(self, ids: List[str]):
        if not self._collection:
            return
        try:
            self._collection.delete(ids=ids)
        except Exception as e:
            logger.error(f"Failed to delete docs: {e}")
            return
        try:
            with self._db() as conn:
                conn.executemany("DELETE FROM chunks WHERE id = ?", [(i,) for i in ids])
        except Exception as e:
            self._lexical_ready = False
            logger.error(f"Failed to update lexical index: {e}")

    def delete_by_source(self, source: str):
        """Remove every chunk that came from one file (used before re-indexing a changed file)."""
        if not self._collection:
            return
        try:
            self._collection.delete(where={"source": source})
            with self._db() as conn:
                conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
        except Exception as e:
            self._lexical_ready = False
            logger.error(f"Failed to delete chunks of {source}: {e}")

    def get_file_signature(self, source: str) -> Optional[str]:
        """Signature (mtime/size/page limit) recorded when ``source`` was last indexed, if any."""
        with self._db() as conn:
            row = conn.execute("SELECT sig FROM indexed_files WHERE source = ?", (source,)).fetchone()
        return row[0] if row else None

    def set_file_signature(self, source: str, sig: str, chunks: int):
        with self._db() as conn:
            conn.execute(
                "INSERT INTO indexed_files(source, sig, chunks) VALUES (?, ?, ?) "
                "ON CONFLICT(source) DO UPDATE SET sig=excluded.sig, chunks=excluded.chunks",
                (source, sig, chunks),
            )

    def indexed_sources(self) -> set:
        """Distinct source paths that already have chunks in the store."""
        self.ensure_lexical_index()
        with self._db() as conn:
            return {r[0] for r in conn.execute("SELECT DISTINCT source FROM chunks")}

    # ------------------------------------------------------------------ read path

    def query_similar(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """
        Semantic search.
        """
        if not self._collection:
            return []

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results
            )

            # Flatten results structure
            # results['ids'][0], results['documents'][0], results['metadatas'][0], results['distances'][0]
            if not results['ids']:
                return []

            flat_results = []
            for i in range(len(results['ids'][0])):
                flat_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            return flat_results

        except Exception as e:
            logger.error(f"Vector Query failed: {e}")
            return []

    def query_lexical(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """Keyword search (BM25 over the FTS5 index)."""
        match = build_fts_query(query_text)
        if not match or not self._collection:
            return []
        try:
            self.ensure_lexical_index()
            with self._db() as conn:
                rows = conn.execute(
                    "SELECT c.id, c.text, c.source, c.page FROM chunks_fts "
                    "JOIN chunks c ON c.rowid = chunks_fts.rowid "
                    "WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
                    (match, n_results),
                ).fetchall()
        except Exception as e:
            logger.error(f"Lexical query failed: {e}")
            return []
        out = []
        for doc_id, text, source, page in rows:
            meta = {"source": source, "filename": os.path.basename(source)}
            if page is not None:
                meta["page"] = page
            out.append({"id": doc_id, "content": text, "metadata": meta, "distance": None})
        return out

    def query_hybrid(self, query_text: str, n_results: int = 5, candidates: int = 50) -> List[Dict]:
        """Dense + BM25 retrieval fused with Reciprocal Rank Fusion.

        Each retriever contributes its top ``candidates`` chunks; chunks found by both rank highest.
        Every result carries ``score`` (RRF) and ``found_by`` (which retrievers returned it).
        """
        dense = self.query_similar(query_text, n_results=candidates)
        lexical = self.query_lexical(query_text, n_results=candidates)
        by_id: Dict[str, Dict] = {}
        found_by: Dict[str, List[str]] = {}
        for label, hits in (("dense", dense), ("lexical", lexical)):
            for hit in hits:
                by_id.setdefault(hit["id"], hit)
                if label == "dense":
                    by_id[hit["id"]] = hit  # prefer Chroma's metadata and distance
                found_by.setdefault(hit["id"], []).append(label)
        scores = rrf_fuse([[h["id"] for h in dense], [h["id"] for h in lexical]])
        ranked = sorted(scores, key=lambda i: scores[i], reverse=True)[:n_results]
        return [dict(by_id[i], score=round(scores[i], 6), found_by=found_by[i]) for i in ranked]

    def count(self):
        if not self._collection:
            return 0
        return self._collection.count()


_default_store: Optional[VectorStoreManager] = None
_default_lock = threading.Lock()


def get_default_store() -> VectorStoreManager:
    """Process-wide store at CHROMA_PERSIST_DIR (default /app/data/chroma_db)."""
    global _default_store
    with _default_lock:
        if _default_store is None:
            _default_store = VectorStoreManager(os.getenv("CHROMA_PERSIST_DIR", DEFAULT_PERSIST_DIR))
        return _default_store
