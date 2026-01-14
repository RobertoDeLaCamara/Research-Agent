# Quick Reference: Common Fixes

## Import Pattern Reference

### ✅ Correct Import Patterns

```python
# In src/agent.py
from .tools.youtube_tools import search_videos_node
from .tools.reporting_tools import generate_report_node
from .state import AgentState
from .db_manager import init_db

# In src/tools/research_tools.py
from ..state import AgentState
from ..utils import api_call_with_retry
from ..config import settings
from .router_tools import update_next_node

# In src/tools/router_tools.py
from ..state import AgentState
from .translation_tools import expand_queries_multilingual

# In tests/test_agent.py
from src.agent import app, initialize_state_node
from src.state import AgentState
```

### ❌ Incorrect Import Patterns (Current)

```python
# DON'T DO THIS:
from tools.youtube_tools import search_videos_node  # Missing dot
from state import AgentState  # Missing parent reference
from db_manager import init_db  # Missing dot
```

---

## Error Handling Patterns

### ✅ Good Error Handling

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def safe_api_call(url: str) -> Optional[dict]:
    """Make API call with proper error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        logger.error(f"Timeout calling {url}")
        return None
    except requests.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e}")
        return None
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from {url}")
        return None
```

### ❌ Bad Error Handling (Current)

```python
# DON'T DO THIS:
try:
    result = some_function()
except:  # Bare except catches everything, even KeyboardInterrupt!
    pass  # Silent failure, no logging
```

---

## Thread Safety Patterns

### ✅ Thread-Safe Pattern

```python
import threading
from typing import Optional, Any

def execute_with_timeout(func: callable, timeout: int = 30) -> Optional[Any]:
    """Execute function with timeout using thread-safe pattern."""
    result_container = []
    error_container = []
    
    def wrapper():
        try:
            result_container.append(func())
        except Exception as e:
            error_container.append(e)
            logger.error(f"Thread execution failed: {e}")
    
    thread = threading.Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        logger.warning(f"Thread timed out after {timeout}s")
        return None
    
    if error_container:
        logger.error(f"Thread failed: {error_container[0]}")
        return None
    
    return result_container[0] if result_container else None
```

### ❌ Unsafe Pattern (Current)

```python
# DON'T DO THIS:
def run_search():
    nonlocal results  # Race condition risk
    results = search()

thread = threading.Thread(target=run_search)
thread.start()
thread.join(timeout=45)
# results might not be set if timeout occurs
```

---

## Configuration Patterns

### ✅ Centralized Configuration

```python
# src/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    
    # Timeout Configuration
    web_search_timeout: int = 45
    llm_request_timeout: int = 60
    content_fetch_timeout: int = 3
    thread_execution_timeout: int = 30
    
    # Content Limits
    max_synthesis_context_chars: int = 25000
    max_content_preview_chars: int = 5000
    max_results_per_source: int = 5
    
    # Research Keywords
    research_trigger_keywords: List[str] = [
        "investiga", "busca", "más información",
        "research", "search", "investigate"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Usage in other files:
from .config import settings

timeout = settings.web_search_timeout
max_chars = settings.max_synthesis_context_chars
```

### ❌ Hardcoded Values (Current)

```python
# DON'T DO THIS:
thread.join(timeout=45)  # Magic number
MAX_CHARS = 25000  # Hardcoded constant
res["content"] = jina_res.text[:5000]  # Magic number
```

---

## Logging Patterns

### ✅ Structured Logging

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def research_operation(topic: str, sources: list):
    """Example of good logging."""
    logger.info(
        f"Starting research: topic='{topic}', "
        f"sources={sources}, "
        f"timestamp={datetime.now().isoformat()}"
    )
    
    try:
        results = perform_research(topic, sources)
        logger.info(
            f"Research completed: topic='{topic}', "
            f"results_count={len(results)}"
        )
        return results
    except Exception as e:
        logger.error(
            f"Research failed: topic='{topic}', "
            f"error={str(e)}, "
            f"error_type={type(e).__name__}"
        )
        raise
```

### ❌ Inconsistent Logging (Current)

```python
# DON'T DO THIS:
print(f"Buscando en la web para: {search_topic}")  # Should use logger
logger.info("Starting web search...")  # Inconsistent with above
# No error logging
```

---

## Input Validation Patterns

### ✅ Pydantic Validation

```python
from pydantic import BaseModel, validator, Field
from typing import Literal

class ResearchRequest(BaseModel):
    """Validated research request."""
    topic: str = Field(..., min_length=3, max_length=500)
    research_depth: Literal["quick", "standard", "deep"] = "standard"
    persona: Literal["general", "business", "tech", "academic", "pm"] = "general"
    
    @validator('topic')
    def validate_topic(cls, v):
        """Prevent injection attacks."""
        forbidden = ['<script>', 'javascript:', 'onerror=', '<?php']
        if any(f in v.lower() for f in forbidden):
            raise ValueError("Invalid characters in topic")
        return v.strip()
    
    @validator('topic')
    def validate_not_empty(cls, v):
        """Ensure topic is not just whitespace."""
        if not v.strip():
            raise ValueError("Topic cannot be empty")
        return v

# Usage:
try:
    request = ResearchRequest(
        topic=user_input,
        research_depth=depth,
        persona=persona
    )
    # request.topic is now validated and safe
except ValidationError as e:
    logger.error(f"Invalid request: {e}")
    return {"error": str(e)}
```

### ❌ No Validation (Current)

```python
# DON'T DO THIS:
topic = request.get("topic")  # No validation
# Directly use in queries - SQL injection risk!
```

---

## File Upload Security

### ✅ Secure File Upload

```python
import os
from pathlib import Path
from typing import List

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = "./knowledge_base"

def secure_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal."""
    # Remove path components
    filename = os.path.basename(filename)
    # Keep only safe characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
    filename = "".join(c if c in safe_chars else "_" for c in filename)
    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename[1:]
    return filename

def validate_and_save_upload(uploaded_file) -> tuple[bool, str]:
    """Validate and save uploaded file securely."""
    # Validate extension
    file_ext = Path(uploaded_file.name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"File type {file_ext} not allowed"
    
    # Validate size
    if uploaded_file.size > MAX_FILE_SIZE:
        return False, f"File too large: {uploaded_file.size / 1024 / 1024:.1f}MB"
    
    # Sanitize filename
    safe_name = secure_filename(uploaded_file.name)
    if not safe_name:
        return False, "Invalid filename"
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Build safe path
    safe_path = os.path.join(UPLOAD_DIR, safe_name)
    
    # Prevent directory traversal
    if not os.path.abspath(safe_path).startswith(os.path.abspath(UPLOAD_DIR)):
        return False, "Invalid file path"
    
    # Save file
    try:
        with open(safe_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True, f"File saved: {safe_name}"
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return False, f"Save failed: {str(e)}"

# Usage in Streamlit:
for uploaded_file in uploaded_files:
    success, message = validate_and_save_upload(uploaded_file)
    if success:
        st.success(message)
    else:
        st.error(message)
```

### ❌ Insecure Upload (Current)

```python
# DON'T DO THIS:
for uploaded_file in uploaded_files:
    # No validation!
    with open(os.path.join(kb_path, uploaded_file.name), "wb") as f:
        f.write(uploaded_file.getbuffer())
    # Directory traversal vulnerability: ../../../etc/passwd
```

---

## Database Patterns

### ✅ Safe Database Operations

```python
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Tuple

DB_PATH = "research_sessions.db"

@contextmanager
def get_db_connection():
    """Provide database connection with automatic cleanup."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def save_session_safe(topic: str, persona: str, state: dict) -> Optional[int]:
    """Save session with parameterized query."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO sessions (topic, persona, timestamp, state_json)
                VALUES (?, ?, datetime('now'), ?)
                ''',
                (topic, persona, json.dumps(state))
            )
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return None

def get_sessions_safe(limit: int = 10) -> List[Tuple]:
    """Get sessions with parameterized query."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, topic, persona, timestamp 
                FROM sessions 
                ORDER BY timestamp DESC 
                LIMIT ?
                ''',
                (limit,)
            )
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        return []
```

### ❌ Unsafe Database (Current)

```python
# DON'T DO THIS:
conn = sqlite3.connect(DB_PATH)  # No context manager
cursor = conn.cursor()
cursor.execute(f"SELECT * FROM sessions WHERE topic = '{topic}'")  # SQL injection!
conn.close()  # Might not execute if error occurs
```

---

## Testing Patterns

### ✅ Good Test Structure

```python
import pytest
from unittest.mock import Mock, patch
from src.agent import app, initialize_state_node
from src.state import AgentState

@pytest.fixture
def sample_state():
    """Provide a complete sample state."""
    return {
        "topic": "Test Topic",
        "research_depth": "quick",
        "persona": "general",
        "research_plan": ["web", "wiki"],
        "iteration_count": 0
    }

@pytest.fixture
def mock_ollama():
    """Mock Ollama responses."""
    with patch('src.tools.router_tools.ChatOllama') as mock:
        mock.return_value.invoke.return_value.content = '["web", "wiki"]'
        yield mock

def test_initialize_state_adds_defaults(sample_state):
    """Test that initialization adds all required fields."""
    result = initialize_state_node(sample_state)
    
    assert result["topic"] == "Test Topic"
    assert "web_research" in result
    assert "wiki_research" in result
    assert isinstance(result["summaries"], list)
    assert result["iteration_count"] == 0

def test_research_with_mocked_llm(sample_state, mock_ollama):
    """Test research flow with mocked LLM."""
    result = app.invoke(sample_state)
    
    assert result["report"]
    assert mock_ollama.called

@pytest.mark.asyncio
async def test_async_research():
    """Test async research operations."""
    # Test async code
    pass

def test_error_handling():
    """Test that errors are handled gracefully."""
    invalid_state = {"topic": ""}  # Invalid
    
    with pytest.raises(ValueError):
        initialize_state_node(invalid_state)
```

---

## Environment Setup

### ✅ Secure Environment Configuration

```bash
# .env.example (commit this)
# API Keys (get from respective services)
TAVILY_API_KEY=your_tavily_key_here
YOUTUBE_API_KEY=your_youtube_key_here
GITHUB_TOKEN=your_github_token_here

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:14b

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_RECIPIENT=recipient@example.com

# .env (NEVER commit this)
# Copy from .env.example and fill with real values

# .gitignore (verify these are present)
.env
.env.local
*.key
*.pem
secrets/
```

---

## Quick Command Reference

```bash
# Fix imports
./fix_critical_issues.sh

# Run tests
python3 -m pytest tests/ -v

# Run specific test
python3 -m pytest tests/test_agent.py::test_initialize_state_node -v

# Check code style
flake8 src/ --max-line-length=120

# Type checking
mypy src/

# Security scan
bandit -r src/

# Start app
streamlit run src/app.py

# Docker
docker compose up -d
docker compose logs -f
docker compose down
```

---

## Common Pitfalls to Avoid

1. ❌ Bare `except:` clauses
2. ❌ Hardcoded credentials
3. ❌ Magic numbers without constants
4. ❌ `print()` instead of `logger`
5. ❌ No input validation
6. ❌ SQL string concatenation
7. ❌ Unsanitized file paths
8. ❌ Missing type hints
9. ❌ No error logging
10. ❌ Inconsistent import patterns

---

## Resources

- [Python Import System](https://docs.python.org/3/reference/import.html)
- [Pydantic Validation](https://docs.pydantic.dev/latest/)
- [Python Logging](https://docs.python.org/3/library/logging.html)
- [OWASP Security](https://owasp.org/www-project-top-ten/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
