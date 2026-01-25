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
    
    kb_path = "./knowledge_base"
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

    # ---------------------------------------------------------
    # SQLITE CACHE IMPLEMENTATION
    # ---------------------------------------------------------
    DB_FILE = "/app/data/rag_cache.db"

    def init_db():
        """Initialize the SQLite database for RAG cache."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                # Table for file metadata (path, hash, last_seen)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        path TEXT PRIMARY KEY,
                        hash TEXT,
                        last_seen REAL
                    )
                """)
                # Table for content (path, text). 
                # Ideally FTS5, but standard table is safer for compatibility.
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
    
    # Batch check cache using DB
    # We want to know which files in 'files_found' are NOT in DB or have different hash
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Get all existing paths and hashes
            # For 10k files, this dict is small enough.
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
            pass # File might have vanished

    # Define Process Function (for threads)
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

    # Process Misses
    new_data = [] # List of dicts to insert to DB
    
    if files_to_process:
        logger.info(f"Processing {len(files_to_process)} new/modified files...")
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(process_file_content, f): f for f in files_to_process}
            
            for future in as_completed(future_to_file):
                processed_count += 1
                file_path = future_to_file[future]
                fname = os.path.basename(file_path)
                update_status(processed_count, len(files_to_process), fname)
                
                try:
                    res = future.result()
                    if res:
                        new_data.append(res)
                        logger.info(f"Processed: {res['filename']}")
                except Exception:
                    pass

    # Batch Insert/Update DB
    if new_data:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                timestamp = time.time()
                # Upsert into files and content
                for item in new_data:
                    conn.execute("INSERT OR REPLACE INTO files (path, hash, last_seen) VALUES (?, ?, ?)", 
                                 (item["path"], item["hash"], timestamp))
                    conn.execute("INSERT OR REPLACE INTO content (path, text) VALUES (?, ?)", 
                                 (item["path"], item["content"]))
                conn.commit()
            logger.info(f"Updated DB with {len(new_data)} records.")
        except Exception as e:
            logger.error(f"DB Write Error: {e}")

    # Retrieval / Search
    # Iterate DB to find relevant content
    # We do this logic in Python to maintain consistency with previous keyword scoring
    # But we stream from DB to avoid memory bloom
    
    update_status(total_files, total_files, "Buscando en BD...", force=True)
    
    topic_words = topic.split()
    results = []
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # We only care about files that are currently present on disk (files_found)
            # Efficient implementation: If files_found is large, we can loop in python, or pass chunks to SQL IN clause.
            # For simplicity: Select all content, filter by path existence in set(files_found) if needed, 
            # OR just assume knowledge base is source of truth and we might have stale entries in DB (garbage collection is separate task).
            # Let's iterate all content in DB. 
            
            cursor = conn.cursor()
            cursor.execute("SELECT path, text FROM content")
            
            # Use Set for O(1) existence check
            valid_files = set(files_found)
            
            for path, content in cursor:
                # Skip if file was deleted from disk
                if path not in valid_files:
                    continue
                    
                filename = os.path.basename(path)
                filename_score = sum(1 for word in topic_words if word in filename.lower())
                
                if not content: continue
                
                # Check match
                content_lower = content.lower()
                if any(word in content_lower for word in topic_words) or not topic_words or filename_score > 0:
                    results.append({
                        "title": filename,
                        "content": content[:3000], 
                        "url": f"file://{os.path.abspath(path)}",
                        "score": filename_score,
                        "cache_update": None # No longer used
                    })
    except Exception as e:
        logger.error(f"Search Error: {e}")

    # Final cleanup of status
    if os.path.exists(STATUS_FILE):
        try: os.remove(STATUS_FILE)
        except: pass

    return {
        "local_rag": results, 
        "next_node": update_next_node(state, "local_rag"),
        "source_metadata": {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}
    }
