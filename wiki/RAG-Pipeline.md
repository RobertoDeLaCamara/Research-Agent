# RAG Pipeline

## Overview

The local RAG source (`local_rag`) provides retrieval over user-uploaded documents. It has two modes, selected with `RAG_MODE`:

| Mode | What it does |
|------|--------------|
| `legacy` (default) | Scans `./knowledge_base` on every run: first 50 pages per PDF, keeps every file that contains any word of the topic, returns the first 3000 characters of each. No ranking. |
| `hybrid` | Returns the best `RAG_TOP_K` (default 8) **chunks** from an index: ChromaDB dense search (MiniLM) plus SQLite FTS5 keyword search (BM25), fused with Reciprocal Rank Fusion. Falls back to `legacy` if the index is missing or empty. |

`hybrid` needs the knowledge base to be indexed once with `python -m src.tools.rag_index` (see *Indexing*).

### External books library (optional)

When `BOOKS_RAG_URL` points to a books search service (`GET <url>/api/search?q=...&top_k=N`, as served by pdf-books-mcp), `local_rag` also queries it with the English query. Book chunks come first, followed by the knowledge base results from the mode above. Each chunk is titled `Book (pp. X-Y, Chapter)` and linked as `file://<path>#page=X`. Index and table-of-contents chunks are dropped. If the service does not answer, the run carries on with the knowledge base only. A connection error is retried once with `host.docker.internal` and `127.0.0.1` swapped, so the same URL works inside and outside Docker.

With `BOOKS_RAG_URL` set, the "Include local knowledge base" checkbox starts checked, and the planner always includes `local_rag` when it is enabled. `USE_RAG_DEFAULT` overrides the checkbox default either way.

## File Ingestion

```
./knowledge_base/           (RAG_KB_DIR env var)
  ├── any_doc.pdf
  ├── notes.txt
  └── subdir/
      └── report.pdf

os.walk() → recursive scan
Supported: .pdf (max 50 pages), .txt
Excluded: other extensions (silently skipped)
```

### PDF Processing

```python
reader = pypdf.PdfReader(path)
pages = reader.pages[:50]  # 50 page limit
text = " ".join(page.extract_text() or "" for page in pages)
```

### Caching (JSON file `/app/data/rag_cache.json`)

A JSON dict keyed by file path; each entry stores the file hash (`"{st_mtime}_{st_size}"`) and the extracted text (see `local_rag_node` in `src/tools/rag_tools.py`).

Cache hit: `hash == f"{stats.st_mtime}_{stats.st_size}"` — no re-parse.
Cache miss: re-read file, update the cache entry.
Batch save: 5 files per batch.

## Text Chunking

```python
chunk_size = 1000   # characters
overlap = 100       # characters
start = 0
while start < len(text):
    chunk = text[start : start + chunk_size]
    chunks.append(chunk)
    start += (chunk_size - overlap)  # sliding window
```

## Vector Store (ChromaDB)

```python
# src/tools/vector_store.py: VectorStoreManager
persist_directory = "/app/data/chroma_db"
collection_name   = "rag_knowledge_base"
embedding_model   = "all-MiniLM-L6-v2"   # ~80 MB, DefaultEmbeddingFunction
similarity_metric = "cosine"              # hnsw:space

# Operations
add_documents(documents)    → client.upsert(ids, texts, metadatas)
query_similar(text, n=5)    → distances + documents
count()                     → collection.count()
delete_documents(ids)       → collection.delete(ids)
```

Chunks are stored as ChromaDB documents with file path and chunk index as metadata.

## Hybrid Retrieval

```python
# src/tools/vector_store.py: VectorStoreManager.query_hybrid(query, n_results, candidates=50)
dense   = query_similar(query, candidates)    # Chroma, cosine over MiniLM embeddings
lexical = query_lexical(query, candidates)    # SQLite FTS5, bm25(); stopwords removed, terms OR-ed
score   = sum(1 / (60 + rank) for each list the chunk appears in)   # Reciprocal Rank Fusion
# returns [{id, content, metadata, distance, score, found_by: ["dense", "lexical"]}]
```

`local_rag_node` (mode `hybrid`) over-fetches 3 x `RAG_TOP_K` hits, drops junk chunks
(table-of-contents dot leaders, broken characters, long runs without real words) and returns
`{title: "book.pdf (p. 7)", content, url: "file://...#page=7", score}`.

Why both retrievers: on a 198-question benchmark over 33,949 chunks of the real knowledge base,
dense alone reached R@5 0.68 / R@10 0.73; BM25 alone 0.67 / 0.76; the fusion 0.73 / 0.85 (hybrid
minus dense: +0.05 R@5 and +0.12 R@10, both with 95% bootstrap CIs above zero). Reproduce with
`python scripts/eval_retrieval.py --persist-dir <copy of chroma_db> --questions questions.jsonl`.
The benchmark questions were LLM-written from the chunks, which favours keyword matching, so treat
the absolute numbers as optimistic.

## Indexing

```bash
python -m src.tools.rag_index                  # new or changed files under $RAG_KB_DIR
python -m src.tools.rag_index --only-missing   # skip files that already have chunks
python -m src.tools.rag_index --max-pages 300  # cap pages per PDF (default: all)
```

- Chunks: 1000 characters, 100 overlap, id `<source>_<n>`, metadata `source`, `filename`, `page`.
- Re-indexing a file first deletes its old chunks, so changed files are replaced, never duplicated.
- Unchanged files are skipped using `mtime_size_maxpages`, stored in `indexed_files` inside the
  keyword database (`rag_lexical.db`, next to `chroma_db`).
- The keyword index is rebuilt from Chroma automatically when the two disagree on the chunk count,
  so an existing Chroma collection works without re-embedding anything.
- Encrypted PDFs are opened with an empty password; those that need a real one are reported as failed.

## Progress Tracking

Long ingestion runs write progress to `/app/data/rag_status.json`:

```json
{"current": 42, "total": 150, "last_file": "report.pdf"}
```

Streamlit polls this file every 0.2 seconds to render the progress bar. Updates are throttled to 0.1s minimum intervals and protected with `threading.Lock()`.

## Thread Safety

- ChromaDB `PersistentClient` is thread-safe
- SQLite connections opened per-operation via context manager (not shared)
- Worker pool: 2 threads (reduced from default to prevent OOM during PDF parsing)

## File Upload (Streamlit)

Users upload files via the sidebar:

```
Supported: .pdf, .txt
Max size: config.max_file_size_mb (default: 10 MB)
Destination: ./knowledge_base/ (RAG_KB_DIR), base name only
Trigger: if use_rag checked → adds "local_rag" to research_plan
```

Uploaded files are immediately available for the next research run. The cache is checked on each ingestion; previously indexed files are not re-parsed.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_KB_DIR` | `./knowledge_base` | Directory scanned for documents |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma_db` | ChromaDB persistence directory (keyword index goes next to it) |
| `RAG_MODE` | `legacy` | `legacy` (file scan) or `hybrid` (Chroma + BM25 chunks) |
| `RAG_TOP_K` | `8` | Chunks returned in `hybrid` mode |
| `BOOKS_RAG_URL` | unset | Books search service; enables the external books library |
| `BOOKS_RAG_TIMEOUT` | `45` | Seconds per books search request |
| `USE_RAG_DEFAULT` | on if `BOOKS_RAG_URL` set | Default for the local knowledge checkbox (`true`/`false`) |
| `RAG_INDEX_MAX_PAGES` | all | Page cap per PDF for `rag_index` |

Uploads are checked by `src/uploads.py`: `MAX_FILE_SIZE_MB` (default 10) and `ALLOWED_FILE_EXTENSIONS` (default `.pdf`, `.txt`). Rejected files get a warning and are not saved.
