import pytest
import os
import sqlite3
from src.db_manager import init_db, save_session, get_recent_sessions, load_session, DB_PATH

@pytest.fixture
def clean_db():
    test_db_path = "test_research_sessions.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    # Initialize with test path
    init_db(db_path=test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

def test_db_initialization(clean_db):
    db_path = clean_db
    assert os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
    assert cursor.fetchone() is not None
    conn.close()

def test_save_and_load_session(clean_db):
    db_path = clean_db
    topic = "Test Topic"
    persona = "tech"
    state = {"topic": topic, "persona": persona, "data": "test_data"}
    
    save_session(topic, persona, state, db_path=db_path)
    
    sessions = get_recent_sessions(db_path=db_path)
    assert len(sessions) == 1
    assert sessions[0][1] == topic
    assert sessions[0][2] == persona
    
    session_id = sessions[0][0]
    loaded_state = load_session(session_id, db_path=db_path)
    assert loaded_state["topic"] == topic
    assert loaded_state["persona"] == persona
    assert loaded_state["data"] == "test_data"

def test_recent_sessions_limit(clean_db):
    db_path = clean_db
    for i in range(15):
        save_session(f"Topic {i}", "general", {"topic": f"Topic {i}"}, db_path=db_path)
    
    sessions = get_recent_sessions(limit=5, db_path=db_path)
    assert len(sessions) == 5
    assert sessions[0][1] == "Topic 14" # Check ordering (DESC)

def test_clear_history(clean_db):
    db_path = clean_db
    from src.db_manager import clear_history
    save_session("Save Me", "general", {}, db_path=db_path)
    save_session("Save Me too", "general", {}, db_path=db_path)
    
    assert len(get_recent_sessions(db_path=db_path)) == 2
    
    clear_history(db_path=db_path)
    assert len(get_recent_sessions(db_path=db_path)) == 0
