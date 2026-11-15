# src/tools/rag_tools.py

import os
import re
import logging
import pypdf
from ..state import AgentState
from .router_tools import update_next_node

logger = logging.getLogger(__name__)


LOCAL_RAG_META = {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}

_JUNK_CHAPTER_TERMS = frozenset({
    "index", "contents", "table of contents", "brief contents",
    "preface", "foreword", "acknowledgements", "acknowledgments",
    "references", "bibliography", "copyright", "title page",
    "dedication", "list of abbreviations", "list of acronyms",
    "about the authors", "contributors",
})

_RAG_STOPWORDS = frozenset({
    "de", "del", "la", "las", "el", "los", "en", "un", "una", "unos", "unas",
    "por", "para", "con", "sin", "sobre", "entre", "hacia", "como", "mas", "más",
    "estado", "arte", "evolucion", "evolución", "estandarizacion", "estandarización",
    "the", "and", "or", "in", "on", "of", "for", "to", "with", "by", "from", "at",
    "as", "into", "about", "state", "art", "evolution", "standardization",
    "redes", "networks", "network", "sistema", "sistemas", "systems",
    "test", "topic",
})

_DOMAIN_ANCHOR_TERMS = frozenset({
    "agentic", "agentica", "agéntica", "llm", "nwdaf", "mdaf", "udm", "nssf",
    "pcf", "ausf", "sdn", "nfv", "iot", "m2m", "hopfield", "blockchain",
    "kubernetes", "docker", "langchain", "langgraph", "ietf", "etsi", "ran",
})

_TEST_DUMMY_FILENAMES = frozenset({"test_doc.txt", "transport_concept.txt"})


def _fix_mojibake(text: str) -> str:
    """Repair UTF-8 strings that were decoded as Latin-1/CP1252 (e.g. 'EconomÃ­a' -> 'Economía')."""
    if not text or "Ã" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _is_junk_chapter(chapter: str) -> bool:
    """Return True if a book chapter label corresponds to front/back matter (Preface, References, TOC, etc.)."""
    chap_lower = _fix_mojibake(chapter or "").strip().lower()
    if not chap_lower:
        return False
    if chap_lower in _JUNK_CHAPTER_TERMS:
        return True
    cleaned = re.sub(r"^[\d.\s-]+", "", chap_lower).strip()
    if cleaned in _JUNK_CHAPTER_TERMS:
        return True
    return any(
        chap_lower.endswith(f", {t}") or chap_lower.endswith(f" {t}") or chap_lower.startswith(f"{t} ")
        for t in ("preface", "references", "bibliography", "index", "table of contents", "acknowledgements", "acknowledgments")
    )


def _extract_query_keywords(topic: str) -> tuple[set[str], set[str]]:
    """Return (all_keywords, anchor_keywords) from a query string."""
    tokens = re.findall(r"[a-z0-9áéíóúñ]{2,}", (topic or "").lower())
    all_kw = {t for t in tokens if len(t) >= 3 and t not in _RAG_STOPWORDS}
    for t in tokens:
        if t in {"5g", "6g", "4g", "3g", "ai", "ia", "ml"}:
            all_kw.add(t)
    anchors = {
        t for t in all_kw
        if any(ch.isdigit() for ch in t) or t in _DOMAIN_ANCHOR_TERMS
    }
    return all_kw, anchors


def _is_book_hit_relevant(book_title: str, chapter: str, text: str, query: str) -> bool:
    """Reject off-topic book chunks (e.g. general Economics books on a 6G/3GPP query)."""
    all_kw, anchors = _extract_query_keywords(query)
    if not anchors:
        return True
    combined = f"{book_title or ''} {chapter or ''} {text or ''}".lower()
    return any(re.search(rf"\b{re.escape(a)}\b", combined) for a in anchors)


def _extract_meaningful_kb_tokens(topic: str, queries: dict | None = None) -> list[str]:
    """Extract meaningful whole-word search tokens (no 1-2 char stopwords like 'en' or 'y')."""
    combined_query = f"{topic or ''} {(queries or {}).get('en', '')} {(queries or {}).get('es', '')}"
    raw_tokens = re.findall(r"[a-z0-9áéíóúñ]{2,}", combined_query.lower())
    out = []
    for tok in raw_tokens:
        if tok in _RAG_STOPWORDS:
            continue
        if len(tok) >= 3 or tok in {"5g", "6g", "4g", "ai", "ia", "ml"}:
            if tok not in out:
                out.append(tok)
    return out


def _books_local_research(topic: str, full_topic: str = ""):
    """Query the local vectorized technical books service (pdf-books-mcp on BOOKS_RAG_URL).

    Returns None if BOOKS_RAG_URL is unset or unreachable so the caller can fall back.
    """
    base_url = (os.getenv("BOOKS_RAG_URL") or "").strip().rstrip("/")
    if not base_url:
        return None
    topic = (topic or "").strip()
    if not topic:
        return []
    try:
        import requests
        from .vector_store import looks_like_junk
        top_k = int(os.getenv("RAG_TOP_K", "8"))
        timeout = float(os.getenv("BOOKS_RAG_TIMEOUT", "45.0"))
        params = {"q": topic, "top_k": str(top_k * 2)}
        url = f"{base_url}/api/search"
        no_proxy = {"http": None, "https": None}
        try:
            resp = requests.get(url, params=params, timeout=timeout, proxies=no_proxy)
        except requests.ConnectionError:
            from ..utils import swap_local_host
            resp = requests.get(swap_local_host(url), params=params, timeout=timeout, proxies=no_proxy)
        resp.raise_for_status()
        raw_hits = resp.json().get("results", [])
    except Exception as e:
        logger.error(f"books_local_rag_failed: {e}")
        return None

    relevance_query = f"{topic} {full_topic}".strip()
    results = []
    for hit in raw_hits:
        text = hit.get("text") or ""
        chapter = _fix_mojibake(hit.get("chapter") or "")
        book_title = _fix_mojibake(hit.get("book_title") or hit.get("file_name") or "Technical Book")
        if looks_like_junk(text) or _is_junk_chapter(chapter):
            continue
        if not _is_book_hit_relevant(book_title, chapter, text, relevance_query):
            continue
        p_start, p_end = hit.get("page_start"), hit.get("page_end")
        if p_start and p_end and p_start != p_end:
            pages = f"pp. {p_start}-{p_end}"
        elif p_start:
            pages = f"p. {p_start}"
        else:
            pages = ""
        chap_str = f", {chapter}" if chapter and chapter != "Unknown" else ""
        loc = f" ({pages}{chap_str})" if pages else (f" ({chapter})" if chap_str else "")
        file_path = hit.get("file_path") or hit.get("file_name") or ""
        url = f"file://{file_path}#page={p_start}" if file_path and p_start else (f"file://{file_path}" if file_path else "")
        results.append({
            "title": f"{book_title}{loc}",
            "content": text,
            "url": url,
            "score": float(hit.get("similarity_score", hit.get("score", 0.0))),
        })
        if len(results) >= top_k:
            break
    logger.info(f"books_local_rag_returned: {len(results)} chunks for '{topic}'")
    return results


def _hybrid_local_research(topic: str):
    """Best chunks for ``topic`` from the hybrid index (dense + BM25), in the shape local_research uses.

    Returns None when the index is unavailable or empty so the caller can fall back to the file scan.
    """
    topic = (topic or "").strip()
    if not topic:
        return []
    try:
        from .vector_store import get_default_store, looks_like_junk
        store = get_default_store()
        if store.count() == 0:
            return None
        from .reranker import rerank_hits, rerank_url
        top_k = int(os.getenv("RAG_TOP_K", "8"))
        reranking = rerank_url() is not None
        # RERANK_URL set: rerank the hybrid top-N (default 30, as benchmarked) with the cross-encoder
        pool = max(top_k, int(os.getenv("RERANK_CANDIDATES", "30"))) if reranking else top_k * 3
        # over-fetch, then drop index/TOC/garbled chunks that match keywords but say nothing
        hits = [h for h in store.query_hybrid(topic, n_results=pool) if not looks_like_junk(h["content"])]
        if reranking:
            hits = rerank_hits(topic, hits)
        hits = hits[:top_k]
    except Exception as e:
        logger.error(f"hybrid_local_rag_failed: {e}")
        return None
    results = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        source, page = meta.get("source") or "", meta.get("page")
        name = meta.get("filename") or os.path.basename(source) or hit["id"]
        url = f"file://{os.path.abspath(source)}" if source else ""
        results.append({
            "title": f"{name} (p. {page})" if page else name,
            "content": hit["content"],
            "url": f"{url}#page={page}" if url and page else url,
            "score": hit.get("score", 0.0),
        })
    return results


def local_rag_node(state: AgentState) -> dict:
    """Local knowledge: the technical books service (BOOKS_RAG_URL) plus the user's ./knowledge_base.

    Book chunks, when the service answers, come first; the knowledge base results follow.
    """
    logger.info("local_rag_node_started")
    result = _knowledge_base_research(state)

    if (os.getenv("BOOKS_RAG_URL") or "").strip():
        q = (state.get("queries") or {}).get("en") or state.get("topic", "")
        books_hits = _books_local_research(q, full_topic=state.get("topic", ""))
        if books_hits is None:
            logger.warning("BOOKS_RAG_URL is set but unreachable; using the local knowledge base only")
        else:
            result["local_research"] = books_hits + (result.get("local_research") or [])
    return result


def _knowledge_base_research(state: AgentState) -> dict:
    """Scans ./knowledge_base and extracts text from PDF and TXT files.

    With RAG_MODE=hybrid it instead returns the best-matching chunks (RAG_TOP_K, default 8) from the
    ChromaDB + BM25 index built by ``python -m src.tools.rag_index``.
    """
    if os.getenv("RAG_MODE", "legacy").strip().lower() == "hybrid":
        hybrid = _hybrid_local_research(state.get("topic", ""))
        if hybrid is not None:
            return {
                "local_research": hybrid,
                "next_node": update_next_node(state, "local_rag"),
                "source_metadata": LOCAL_RAG_META,
            }
        logger.warning("RAG_MODE=hybrid but the index is unavailable or empty; falling back to the file scan")

    kb_path = os.getenv("RAG_KB_DIR", "./knowledge_base")
    if not os.path.exists(kb_path):
        os.makedirs(kb_path)
        logger.info(f"Created knowledge_base directory at {kb_path}")
        return {"local_research": [], "next_node": update_next_node(state, "local_rag"), "source_metadata": {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}}

    topic = state.get("topic", "").lower()
    topic_tokens = _extract_meaningful_kb_tokens(topic, state.get("queries"))

    import json

    # ---------------------------------------------------------
    # CACHE IMPLEMENTATION
    # ---------------------------------------------------------
    CACHE_FILE = "/app/data/rag_cache.json"
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load RAG cache: {e}")

    cache_dirty = False

    def get_file_hash(file_path):
        """Simple hash based on modification time and size."""
        stats = os.stat(file_path)
        return f"{stats.st_mtime}_{stats.st_size}"

    # Updated to support recursive search with os.walk
    files_found = []
    for root, dirs, files in os.walk(kb_path):
        for file in files:
            if file.lower() in _TEST_DUMMY_FILENAMES:
                continue
            if file.lower().endswith(('.pdf', '.txt')):
                files_found.append(os.path.join(root, file))

    logger.info(f"Scanning {len(files_found)} files in knowledge_base (recursive)")

    from concurrent.futures import ThreadPoolExecutor

    def process_file(file_path):
        nonlocal cache_dirty
        filename = os.path.basename(file_path)
        fname_lower = filename.lower()

        # Optimization: Score filename relevance using whole-word token matches
        filename_score = sum(
            1 for word in topic_tokens if re.search(rf"\b{re.escape(word)}\b", fname_lower)
        )

        # -----------------------------------------------------
        # CACHE CHECK
        # -----------------------------------------------------
        file_hash = get_file_hash(file_path)
        cached_entry = cache.get(file_path)

        content = ""

        if cached_entry and cached_entry.get("hash") == file_hash:
            content = cached_entry.get("content", "")
        else:
            try:
                if fname_lower.endswith(".pdf"):
                    with open(file_path, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        max_pages = 50
                        count = 0
                        for page in reader.pages:
                            if count >= max_pages:
                                break
                            text = page.extract_text()
                            if text:
                                content += text + "\n"
                            count += 1
                elif fname_lower.endswith(".txt"):
                    with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
                        content = f.read()

                if content:
                    cache[file_path] = {
                        "hash": file_hash,
                        "content": content
                    }
            except Exception as e:
                logger.error(f"Error reading local file {filename}: {e}")
                return None

        if content:
            content_lower = content.lower()
            if "for rag persistence verification" in content_lower:
                return None
            # Whole-word relevance check against meaningful tokens (avoids matching 'en' in 'document')
            matched_words = sum(
                1 for word in topic_tokens if re.search(rf"\b{re.escape(word)}\b", content_lower)
            )
            if matched_words > 0 or not topic_tokens or filename_score > 0:
                return {
                    "title": filename,
                    "content": content[:3000],
                    "url": f"file://{os.path.abspath(file_path)}",
                    "score": filename_score + matched_words,
                    "cache_update": {file_path: {"hash": file_hash, "content": content}} if not cached_entry or cached_entry.get("hash") != file_hash else None
                }
        return None

    # Status Reporting
    STATUS_FILE = "/app/data/rag_status.json"
    def update_status(current, total, filename):
        try:
            temp_file = STATUS_FILE + ".tmp"
            with open(temp_file, "w") as f:
                json.dump({"current": current, "total": total, "last_file": filename}, f)
            os.replace(temp_file, STATUS_FILE)
        except Exception as e:
            logger.warning(f"Status update failed: {e}")

    processed_count = 0
    total_files = len(files_found)
    update_status(0, total_files, "Iniciando análisis paralelo...")
    logger.info(f"Starting processing of {total_files} files with max_workers=4")

    results = []
    from concurrent.futures import as_completed
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {executor.submit(process_file, f): f for f in files_found}

        for future in as_completed(future_to_file):
            processed_count += 1
            file_path = future_to_file[future]
            fname = os.path.basename(file_path)
            update_status(processed_count, total_files, fname)

            try:
                res = future.result()
                if res:
                    if "cache_update" in res and res["cache_update"]:
                        cache.update(res["cache_update"])
                        cache_dirty = True
                        del res["cache_update"]
                    results.append(res)
                    logger.info(f"Processed: {res['title']}")
            except Exception as e:
                logger.error(f"Error processing {fname}: {e}")

    if os.path.exists(STATUS_FILE):
        try:
            os.remove(STATUS_FILE)
        except OSError:
            pass

    if cache_dirty:
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            logger.info(f"Updated RAG cache at {CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save RAG cache: {e}")

    return {
        "local_research": results,
        "next_node": update_next_node(state, "local_rag"),
        "source_metadata": {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}
    }
