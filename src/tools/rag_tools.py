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
        return {"local_research": [], "next_node": update_next_node(state, "local_rag")}

    results = []
    topic = state.get("topic", "").lower()
    
    import json
    import time
    
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
            if file.lower().endswith(('.pdf', '.txt')):
                files_found.append(os.path.join(root, file))
    
    logger.info(f"Scanning {len(files_found)} files in knowledge_base (recursive)")
    
    from concurrent.futures import ThreadPoolExecutor
    
    def process_file(file_path):
        nonlocal cache_dirty
        filename = os.path.basename(file_path)
        
        # Optimization: Score filename relevance
        topic_words = topic.split()
        filename_score = sum(1 for word in topic_words if word in filename.lower())
        
        # -----------------------------------------------------
        # CACHE CHECK
        # -----------------------------------------------------
        file_hash = get_file_hash(file_path)
        cached_entry = cache.get(file_path)
        
        content = ""
        
        if cached_entry and cached_entry.get("hash") == file_hash:
            # Cache Hit
            content = cached_entry.get("content", "")
            # logger.debug(f"Cache hit for {filename}")
        else:
            # Cache Miss - Process File
            try:
                if filename.lower().endswith(".pdf"):
                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        # Limit pages to avoid huge delays on massive books
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
                
                # Update Cache if content found
                if content:
                    cache[file_path] = {
                        "hash": file_hash,
                        "content": content
                    }
                    # We can't easily set nonlocal cache_dirty in threaded context safely without lock
                    # But since we're using ThreadPoolExecutor, we can just return the cache update 
                    # from the function and handle it in the main thread? 
                    # Actually, dictionary operations in Python are atomic-ish, but let's be safe.
                    # We will re-save the whole cache at the end, so modifying 'cache' dict here is okay 
                    # as long as we don't have race conditions on the same key (unlikely).
            except Exception as e:
                logger.error(f"Error reading local file {filename}: {e}")
                return None

        if content:
            # Basic relevance check
            if any(word in content.lower() for word in topic_words) or not topic_words or filename_score > 0:
                return {
                    "title": filename,
                    "content": content[:3000], 
                    "url": f"file://{os.path.abspath(file_path)}",
                    "score": filename_score,
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

    # Use ThreadPoolExecutor
    processed_count = 0
    total_files = len(files_found)
    update_status(0, total_files, "Iniciando análisis paralelo...")
    logger.info(f"Starting processing of {total_files} files with max_workers=4")
    
    # Reduced workers to prevent OOM on large PDFs
    from concurrent.futures import as_completed
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {executor.submit(process_file, f): f for f in files_found}
        
        for future in as_completed(future_to_file):
            processed_count += 1
            file_path = future_to_file[future]
            fname = os.path.basename(file_path)
            # Update status for every finished file
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
                
    # Final cleanup of status
    if os.path.exists(STATUS_FILE):
        try:
            os.remove(STATUS_FILE)
        except: pass

    # Save Cache...
    if cache_dirty:
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            logger.info(f"Updated RAG cache at {CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save RAG cache: {e}")

    # For now, we store them in a new state key or append to web_research
    # Let's use a specific key for clarity in synthesis
    return {
        "local_research": results, 
        "next_node": update_next_node(state, "local_rag"),
        "source_metadata": {"local_rag": {"source_type": "user_provided_knowledge", "reliability": 5}}
    }
