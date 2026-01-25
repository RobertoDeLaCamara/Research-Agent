# src/tools/rag_tools.py

import os
import logging
from typing import List
import PyPDF2
from ..state import AgentState
from .router_tools import update_next_node

logger = logging.getLogger(__name__)

def local_rag_node(state: AgentState) -> dict:
    """Scans ./knowledge_base and extracts text from PDF and TXT files."""
    print("\n--- 📁 NODO: CONOCIMIENTO LOCAL (RAG) ---")
    
    kb_path = os.getenv("RAG_KB_DIR", "./knowledge_base")
    if not os.path.exists(kb_path):
        os.makedirs(kb_path)
        logger.info(f"Created knowledge_base directory at {kb_path}")
        return {"local_rag": [], "next_node": update_next_node(state, "local_rag")}

    results = []
    topic = state.get("topic", "").lower()
    
    import sqlite3
    import json
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Try importing Vector Store, handle failure gracefully (e.g. if chromadb not installed yet)
    try:
        from .vector_store import VectorStoreManager
        vector_store = VectorStoreManager()
    except ImportError:
        logger.warning("Vector Store dependencies not found. Falling back to Keyword-only search.")
        vector_store = None
    except Exception as e:
        logger.error(f"Vector Store init failed: {e}")
        vector_store = None

    # ---------------------------------------------------------
    # SQLITE CACHE IMPLEMENTATION
    # ---------------------------------------------------------
    DB_FILE = "/app/data/rag_cache.db"

    def init_db():
        """Initialize the SQLite database for RAG cache."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                # Table for file metadata 
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        path TEXT PRIMARY KEY,
                        hash TEXT,
                        last_seen REAL
                    )
                """)
                # Table for content 
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS content (
                        path TEXT PRIMARY KEY,
                        text TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init RAG DB: {e}")

    # Ensure DB exists
    init_db()

    # Helper: Get file hash
    def get_file_hash(file_path):
        """Simple hash based on modification time and size."""
        stats = os.stat(file_path)
        return f"{stats.st_mtime}_{stats.st_size}"

    # Helper: Status Update
    STATUS_FILE = "/app/data/rag_status.json"
    last_status_update = 0
    
    def update_status(current, total, filename, force=False):
        nonlocal last_status_update
        now = time.time()
        # Throttle: 0.1s
        if not force and (now - last_status_update < 0.1):
            return
        try:
            temp_file = STATUS_FILE + ".tmp"
            with open(temp_file, "w") as f:
                json.dump({"current": current, "total": total, "last_file": filename}, f)
            os.replace(temp_file, STATUS_FILE)
            last_status_update = now
        except Exception as e: 
            logger.warning(f"Status update failed: {e}")

    # Scan Files
    files_found = []
    for root, dirs, files in os.walk(kb_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.txt')):
                files_found.append(os.path.join(root, file))
    
    total_files = len(files_found)
    logger.info(f"Scanning {total_files} files in knowledge_base (recursive)")
    update_status(0, total_files, "Comprobando caché...", force=True)

    # Identify Cache Misses
    files_to_process = []
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT path, hash FROM files")
            db_files = {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"DB Read Error: {e}")
        db_files = {}

    for file_path in files_found:
        try:
            current_hash = get_file_hash(file_path)
            if file_path not in db_files or db_files[file_path] != current_hash:
                files_to_process.append(file_path)
        except OSError:
            pass

    # Define Process Function
    def process_file_content(file_path):
        filename = os.path.basename(file_path)
        try:
            content = ""
            if filename.lower().endswith(".pdf"):
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    max_pages = 50 
                    count = 0
                    for page in reader.pages:
                        if count >= max_pages: break
                        text = page.extract_text()
                        if text:
                            content += text + "\n"
                        count += 1
            elif filename.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()
            
            if content:
                file_hash = get_file_hash(file_path)
                return {
                    "path": file_path,
                    "hash": file_hash,
                    "content": content,
                    "filename": filename
                }
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
        return None

    # Process Misses with Batch Saving
    BATCH_SIZE = 5
    current_batch = []
    
    def save_batch(batch_data):
        if not batch_data: return
        
        # SQLite Update
        try:
            with sqlite3.connect(DB_FILE) as conn:
                timestamp = time.time()
                for item in batch_data:
                    conn.execute("INSERT OR REPLACE INTO files (path, hash, last_seen) VALUES (?, ?, ?)", 
                                 (item["path"], item["hash"], timestamp))
                    conn.execute("INSERT OR REPLACE INTO content (path, text) VALUES (?, ?)", 
                                 (item["path"], item["content"]))
                conn.commit()
            logger.info(f"💾 Saved batch of {len(batch_data)} records to SQLite.")
        except Exception as e:
            logger.error(f"DB Write Error: {e}")
            
        # Vector Store Update
        if vector_store:
            try:
                vectors_to_add = []
                for item in batch_data:
                    text = item["content"]
                    # Chunking Logic (Simple: 1000 chars, overlap 100)
                    chunk_size = 1000
                    overlap = 100
                    start = 0
                    chunk_idx = 0
                    
                    while start < len(text):
                        end = min(start + chunk_size, len(text))
                        chunk_text = text[start:end]
                        
                        vectors_to_add.append({
                            "id": f"{item['path']}_{chunk_idx}",
                            "text": chunk_text,
                            "metadata": {"source": item["path"], "filename": item["filename"]}
                        })
                        
                        start += (chunk_size - overlap)
                        chunk_idx += 1
                
                if vectors_to_add:
                    # Update status for vector indexing (just once per batch to avoid spam)
                     # vector_store.add_documents handles batching internally usually, but we pass list
                    vector_store.add_documents(vectors_to_add)
                    logger.info(f"🧠 Indexed {len(vectors_to_add)} vector chunks.")
                    
            except Exception as e:
                logger.error(f"Vector Indexing Error: {e}")

    if files_to_process:
        logger.info(f"Processing {len(files_to_process)} new/modified files...")
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=2) as executor: # Reduced workers to prevent OOM
            future_to_file = {executor.submit(process_file_content, f): f for f in files_to_process}
            
            for future in as_completed(future_to_file):
                processed_count += 1
                file_path = future_to_file[future]
                fname = os.path.basename(file_path)
                update_status(processed_count, len(files_to_process), fname)
                
                try:
                    res = future.result()
                    if res:
                        current_batch.append(res)
                        logger.info(f"Processed: {res['filename']}")
                        
                        # Check Batch Size
                        if len(current_batch) >= BATCH_SIZE:
                            save_batch(current_batch)
                            current_batch = [] # Reset
                            
                except Exception:
                    pass
        
        # Save remaining items
        if current_batch:
            save_batch(current_batch)

    # ---------------------------------------------------------
    # HYBRID RETRIEVAL (Semantic + Keyword)
    # ---------------------------------------------------------
    update_status(total_files, total_files, "Búsqueda Híbrida...", force=True)
    
    final_results = {} # url -> result_dict
    
    # 1. Semantic Search (Vector)
    if vector_store:
        try:
            vector_results = vector_store.query_similar(topic, n_results=5)
            for res in vector_results:
                path = res["metadata"]["source"]
                if path not in final_results:
                    final_results[path] = {
                        "title": res["metadata"]["filename"],
                        "content": res["content"], # Just the chunk
                        "url": f"file://{os.path.abspath(path)}",
                        "score": 10.0 - res["distance"], # Rough conversion
                        "type": "semantic"
                    }
                else:
                    # Append chunk if already exists
                    final_results[path]["content"] += "\n...\n" + res["content"]
                    final_results[path]["score"] += (10.0 - res["distance"])
        except Exception as e:
            logger.error(f"Vector Search Error: {e}")

    # 2. Keyword Search (SQLite)
    # Only if semantic yielded few results, or always? 
    # Let's do ALWAYS to ensure exact matches are found.
    topic_words = topic.split()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT path, text FROM content")
            valid_files = set(files_found)
            
            for path, content in cursor:
                if path not in valid_files: continue
                if path in final_results: continue # Skip if already found by vector (optional strategy)
                
                filename = os.path.basename(path)
                filename_score = sum(1 for word in topic_words if word in filename.lower())
                
                if not content: continue
                content_lower = content.lower()
                
                if any(word in content_lower for word in topic_words) or not topic_words or filename_score > 0:
                     final_results[path] = {
                        "title": filename,
                        "content": content[:3000], 
                        "url": f"file://{os.path.abspath(path)}",
                        "score": filename_score,
                        "type": "keyword"
                    }
    except Exception as e:
        logger.error(f"Keyword Search Error: {e}")

    # Convert to list
    results_list = list(final_results.values())
    
    # Sort by score desc
    results_list.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Cleanup Status
    if os.path.exists(STATUS_FILE):
        try: os.remove(STATUS_FILE)
        except: pass

    return {
        "local_research": results_list, 
        "next_node": update_next_node(state, "local_rag"),
        "source_metadata": {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}
    }
