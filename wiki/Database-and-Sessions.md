# Database and Sessions

## Session Storage

Research sessions are persisted in SQLite via `src/db_manager.py`.

```sql
-- research_sessions.db
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL,
    persona     TEXT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    state_json  TEXT   -- full AgentState as JSON (messages excluded)
);
```

### Serialization

The full `AgentState` dict is serialized to JSON before storage. The `messages` field (list of LangChain `BaseMessage` objects) is excluded — it is not JSON-serializable and is not needed for session replay.

```python
def save_session(topic, persona, state, db_path):
    serializable = {k: v for k, v in state.items() if k != "messages"}
    sanitized = recursive_sanitize(serializable)  # UTF-8 encoding with 'replace'
    json_str = json.dumps(sanitized)
    db.execute("INSERT INTO sessions (topic, persona, state_json) VALUES (?, ?, ?)",
               (topic, persona, json_str))
```

### Session Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `init_db(db_path)` | None | Creates table + triggers 30-day cleanup |
| `save_session(topic, persona, state, db_path)` | None | Insert new session row |
| `get_recent_sessions(limit=10, db_path)` | `List[Tuple]` | `(id, topic, persona, timestamp)` |
| `load_session(session_id, db_path)` | `dict or None` | Deserialize state_json back to dict |
| `clear_history(db_path)` | `bool` | `DELETE FROM sessions` |
| `cleanup_old_sessions(days=30, db_path)` | `int` | Count of deleted rows |

### Auto-cleanup

`init_db()` calls `cleanup_old_sessions(days=30)` on every startup. Sessions older than 30 days are deleted.

### Default Path

```
db_path = "research_sessions.db"   # from settings
# Override via: DB_PATH env var
```

## RAG Cache Storage

A separate SQLite database (`/app/data/rag_cache.db`) tracks which files have been indexed:

```sql
CREATE TABLE files (
    path     TEXT PRIMARY KEY,
    hash     TEXT,     -- "{st_mtime}_{st_size}"
    last_seen REAL
);

CREATE TABLE content (
    path TEXT PRIMARY KEY,
    text TEXT           -- extracted text content
);
```

This is internal to the RAG pipeline — not exposed via API or UI.

## Session Management in Streamlit

The sidebar "Session History" section shows the 10 most recent sessions:

```
[2026-03-30 12:01] | Artificial Intelligence in Education
[2026-03-29 09:15] | Quantum Computing Hardware Landscape
...
```

**Load**: clicking "Load" restores the full state from `state_json` into `st.session_state`. The previous consolidated summary, report, and research results are all restored. Messages are empty (not persisted).

**Clear**: calls `clear_history()` — deletes all rows from `sessions` table.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `db_path` | `research_sessions.db` | Session SQLite file |
| `DB_PATH` env var | — | Override for db_path |
| `cache_expiry_hours` | 24 | (In-memory cache TTL, not DB cleanup) |
| Auto-cleanup | 30 days | Triggered at `init_db()` |
