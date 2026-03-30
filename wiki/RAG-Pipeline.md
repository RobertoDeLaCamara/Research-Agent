# RAG Pipeline

## Overview

The local RAG source (`local_rag`) provides retrieval over user-uploaded documents. It combines ChromaDB vector search (semantic) with SQLite keyword matching. Both paths contribute scored results that are merged and passed to the LLM synthesis context.

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

### Caching (SQLite `rag_cache.db`)

```sql
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    hash TEXT,              -- "{st_mtime}_{st_size}"
    last_seen REAL
);

CREATE TABLE content (
    path TEXT PRIMARY KEY,
    text TEXT
);
```

Cache hit: `hash == f"{stats.st_mtime}_{stats.st_size}"` — no re-parse.
Cache miss: re-read file, update both tables.
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
# Semantic path (ChromaDB)
vector_results = vector_store.query_similar(topic, n_results=5)
# Score = 10.0 - cosine_distance

# Keyword path (SQLite content table)
for path, text in db.execute("SELECT path, text FROM content"):
    filename = os.path.basename(path).lower()
    topic_words = topic.lower().split()
    filename_score = sum(1 for w in topic_words if w in filename)
    # Include if: any topic word in text OR filename matches
    # Content preview: 3000 chars

# Merge and return both result sets
# Result shape: {title, content, url (file://), score, type: "semantic"|"keyword"}
```

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
Destination: ./knowledge_base/
Trigger: if use_rag checked → adds "local_rag" to research_plan
```

Uploaded files are immediately available for the next research run. The cache is checked on each ingestion; previously indexed files are not re-parsed.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_KB_DIR` | `./knowledge_base` | Directory scanned for documents |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma_db` | ChromaDB persistence directory |
| `max_file_size_mb` | 10 | Upload size limit |
| `allowed_file_extensions` | `.pdf`, `.txt`, `.md` | Accepted formats |
