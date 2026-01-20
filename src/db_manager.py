import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

from .config import settings

DB_PATH = settings.db_path

def init_db(db_path: str = DB_PATH) -> None:
    """Initialize the SQLite database and create necessary tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Table for research sessions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        persona TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        state_json TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")
    
    # Trigger automatic cleanup of old sessions
    cleanup_old_sessions(db_path=db_path)

def recursive_sanitize(obj):
    if isinstance(obj, str):
        return obj.encode('utf-8', 'replace').decode('utf-8')
    elif isinstance(obj, dict):
        return {k: recursive_sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_sanitize(v) for v in obj]
    return obj

def save_session(topic: str, persona: str, state: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Save a research state to the database."""
    try:
        # Avoid saving large binary blobs if they exist
        clean_state = state.copy()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Serialize state, skipping non-serializable parts
        state_to_save = {k: v for k, v in clean_state.items() if k != "messages"}
        
        # Sanitize before JSON dump to prevent surrogate errors
        safe_state = recursive_sanitize(state_to_save)
        
        cursor.execute('''
        INSERT INTO sessions (topic, persona, timestamp, state_json)
        VALUES (?, ?, ?, ?)
        ''', (topic, persona, datetime.now().isoformat(), json.dumps(safe_state)))
        
        conn.commit()
        conn.close()
        logger.info(f"Session saved for topic: {topic}")
    except Exception as e:
        logger.error(f"Failed to save session: {e}")

def get_recent_sessions(limit: int = 10, db_path: str = DB_PATH) -> List[Tuple]:
    """Retrieve the most recent research sessions."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, topic, persona, timestamp FROM sessions ORDER BY timestamp DESC LIMIT ?', (limit,))
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        return []

def load_session(session_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Load a full research state from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT state_json FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        return None

def clear_history(db_path: str = DB_PATH) -> bool:
    """Delete all research sessions from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions')
        conn.commit()
        conn.close()
        logger.info("All research history cleared.")
        return True
    except Exception as e:
        logger.error(f"Failed to clear history: {e}")
        return False

def cleanup_old_sessions(days: int = 30, db_path: str = DB_PATH) -> int:
    """Delete research sessions older than a certain number of days."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # timestamp is stored in ISO format or DEFAULT CURRENT_TIMESTAMP
        # SQLite's date functions work well with these
        cursor.execute("DELETE FROM sessions WHERE timestamp < datetime('now', '-' || ? || ' days')", (days,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old research sessions (older than {days} days).")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup old sessions: {e}")
        return 0
