# src/tools/rag_tools.py

import os
import logging
from typing import List
import PyPDF2
from state import AgentState
from tools.research_tools import update_next_node

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
    
    files = os.listdir(kb_path)
    logger.info(f"Scanning {len(files)} files in knowledge_base")

    for filename in files:
        file_path = os.path.join(kb_path, filename)
        content = ""
        
        try:
            if filename.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content += page.extract_text() + "\n"
            elif filename.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            
            if content:
                # Basic relevance check: see if any word from topic is in content
                # This is a very simple 'RAG' for Phase 3.
                topic_words = topic.split()
                if any(word in content.lower() for word in topic_words) or not topic_words:
                    results.append({
                        "title": filename,
                        "content": content[:2000],  # Limit content size
                        "url": f"file://{os.path.abspath(file_path)}"
                    })
                    logger.info(f"Added local file: {filename}")

        except Exception as e:
            logger.error(f"Error reading local file {filename}: {e}")

    # For now, we store them in a new state key or append to web_research
    # Let's use a specific key for clarity in synthesis
    return {"local_research": results, "next_node": update_next_node(state, "local_rag")}
