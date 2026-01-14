# Code Review: Research-Agent 🔬

**Review Date:** January 14, 2026  
**Reviewer:** AI Code Review Assistant  
**Project:** Autonomous Research Agent with LangChain/LangGraph

---

## Executive Summary

**Overall Assessment:** ⭐⭐⭐⭐ (4/5)

The Research-Agent is a well-architected autonomous research system with strong features and good documentation. However, there are **critical import issues** preventing tests from running, along with several security, performance, and code quality concerns that should be addressed.

### Key Strengths
- ✅ Excellent architecture using LangGraph for workflow orchestration
- ✅ Comprehensive multi-source research capabilities
- ✅ Good separation of concerns with modular tool design
- ✅ Strong documentation and README
- ✅ Docker support for easy deployment

### Critical Issues
- 🔴 **BLOCKER:** Import path inconsistencies breaking all tests
- 🔴 **SECURITY:** Exposed API keys and credentials in `.env` file
- 🟡 Missing dependencies in requirements.txt
- 🟡 Inconsistent error handling patterns

---

## 1. Critical Issues (Must Fix)

### 1.1 Import Path Inconsistencies 🔴 BLOCKER

**Severity:** Critical  
**Impact:** All tests fail to run

**Problem:**
The codebase has inconsistent import patterns causing module resolution failures:

```python
# In src/agent.py - uses relative imports without 'src.' prefix
from tools.youtube_tools import search_videos_node  # ❌ FAILS

# In src/tools/research_tools.py - uses absolute imports
from state import AgentState  # ❌ FAILS (should be 'from src.state')

# In tests - uses 'src.' prefix
from src.agent import app  # ✅ CORRECT
```

**Solution:**
Choose ONE consistent import strategy:

**Option A: Relative imports within src/ (Recommended)**
```python
# In src/agent.py
from .tools.youtube_tools import search_videos_node
from .state import AgentState

# In src/tools/research_tools.py
from ..state import AgentState
from ..utils import api_call_with_retry
```

**Option B: Add src/ to PYTHONPATH**
```bash
# In pytest.ini or conftest.py
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
```

**Files to fix:**
- `src/agent.py` (lines 4-13)
- `src/tools/research_tools.py` (line 15)
- `src/tools/router_tools.py` (line 6)
- `src/tools/synthesis_tools.py` (line 5)
- `src/tools/chat_tools.py` (line 5)
- `src/tools/reddit_tools.py` (line 4)
- `src/tools/youtube_tools.py` (line 12)

### 1.2 Security: Exposed Credentials 🔴 CRITICAL

**Severity:** Critical  
**Impact:** Security breach, credential compromise

**Problem:**
The `.env` file contains real API keys and passwords committed to the repository:

```bash
TAVILY_API_KEY=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
GITHUB_TOKEN=REDACTED_TOKEN
EMAIL_PASSWORD=fynx olqi nvjg sqio
```

**Immediate Actions Required:**
1. **REVOKE ALL EXPOSED CREDENTIALS IMMEDIATELY**
   - Regenerate Tavily API key
   - Regenerate GitHub token
   - Change email app password
   - Regenerate YouTube API key

2. **Remove from Git history:**
```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

3. **Update .gitignore:**
```gitignore
# Already present, but verify:
.env
*.key
*.pem
secrets/
```

4. **Use environment-specific files:**
```bash
.env.example  # Template with placeholder values (commit this)
.env          # Real values (NEVER commit)
.env.local    # Local overrides (NEVER commit)
```

### 1.3 Missing Dependencies

**Severity:** High  
**Impact:** Runtime failures

**Problem:**
`requirements.txt` is missing dependencies that are imported:

```python
# Missing from requirements.txt:
- python-docx  # Used in reporting_tools.py
- PyPDF2       # Used in rag_tools.py (note: listed as 'pypdf2' but imported as 'PyPDF2')
```

**Solution:**
```bash
# Add to requirements.txt:
python-docx>=0.8.11
PyPDF2>=3.0.0
```

**Note:** You have both `PyPDF2` and `pypdf2` listed - these are the same package. Remove the duplicate.

---

## 2. High Priority Issues

### 2.1 Database Import Error in Agent

**File:** `src/agent.py` (line 26)  
**Severity:** High

```python
# Current (WRONG):
from db_manager import init_db, save_session

# Should be:
from .db_manager import init_db, save_session
```

### 2.2 Inconsistent Error Handling

**Severity:** Medium  
**Impact:** Difficult debugging, silent failures

**Examples:**

```python
# src/tools/research_tools.py (line 30)
try:
    from config import settings
    tavily_key = settings.tavily_api_key
except:  # ❌ Bare except catches everything
    import os
    tavily_key = os.getenv("TAVILY_API_KEY")
```

**Recommendation:**
```python
try:
    from .config import settings
    tavily_key = settings.tavily_api_key
except (ImportError, AttributeError) as e:
    logger.warning(f"Failed to load config: {e}, falling back to env vars")
    tavily_key = os.getenv("TAVILY_API_KEY")
```

### 2.3 Thread Safety Issues

**File:** `src/tools/research_tools.py` (lines 50-75)  
**Severity:** Medium

**Problem:**
Using `nonlocal` with threading can cause race conditions:

```python
def run_web_search():
    nonlocal results  # ⚠️ Potential race condition
    try:
        # ... search logic
        results = list(executor.map(enhance_result, raw_results))
```

**Recommendation:**
Use thread-safe data structures or return values:

```python
def run_web_search():
    local_results = []
    try:
        # ... search logic
        local_results = list(executor.map(enhance_result, raw_results))
    except Exception as e:
        logger.error(f"Web search failed: {e}")
    return local_results

# Then in the main function:
result_container = []
thread = threading.Thread(target=lambda: result_container.append(run_web_search()))
```

### 2.4 Hardcoded Timeout Values

**Files:** Multiple  
**Severity:** Medium

**Problem:**
Timeout values are scattered throughout the code:

```python
thread.join(timeout=45)  # research_tools.py
request_timeout=60       # router_tools.py
timeout=3                # Jina Reader calls
```

**Recommendation:**
Centralize in `config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings
    
    # Timeout Configuration
    web_search_timeout: int = 45
    llm_request_timeout: int = 60
    content_fetch_timeout: int = 3
    thread_execution_timeout: int = 30
```

---

## 3. Code Quality Issues

### 3.1 Inconsistent Logging

**Severity:** Low  
**Impact:** Difficult debugging

**Problem:**
Mix of `print()` and `logger` statements:

```python
# src/tools/research_tools.py
print(f"Buscando en la web (Tavily) para: {search_topic}")  # ❌
logger.info("Starting web search...")  # ✅
```

**Recommendation:**
Use logging consistently:

```python
logger.info(f"Searching web (Tavily) for: {search_topic}")
```

### 3.2 Magic Numbers and Strings

**Examples:**

```python
# src/tools/synthesis_tools.py
MAX_CHARS = 25000  # Should be in config

# src/tools/research_tools.py
res["content"] = jina_res.text[:5000]  # Magic number

# src/agent.py
if any(kw in text for kw in ["investiga", "busca", "más información", "research", "search"]):
    # Hardcoded keywords
```

**Recommendation:**
Move to configuration:

```python
# config.py
class Settings(BaseSettings):
    max_synthesis_context_chars: int = 25000
    max_content_preview_chars: int = 5000
    research_trigger_keywords: List[str] = [
        "investiga", "busca", "más información", 
        "research", "search", "investigate"
    ]
```

### 3.3 Incomplete Type Hints

**Severity:** Low  
**Impact:** Reduced IDE support, harder maintenance

**Examples:**

```python
# src/utils.py
def api_call_with_retry(func, *args, **kwargs):  # ❌ No return type
    """Retry failed API calls with exponential backoff."""
    
# Should be:
def api_call_with_retry(func: Callable, *args, **kwargs) -> Any:
    """Retry failed API calls with exponential backoff."""
```

### 3.4 Long Functions

**File:** `src/tools/reporting_tools.py`  
**Function:** `generate_report_node` (200+ lines)

**Recommendation:**
Break into smaller functions:

```python
def generate_report_node(state: AgentState) -> dict:
    """Main report generation orchestrator."""
    html_header = _generate_html_header(state["topic"])
    html_body = _generate_html_body(state)
    html_footer = _generate_html_footer()
    
    return {"report": html_header + html_body + html_footer}

def _generate_html_header(topic: str) -> str:
    """Generate HTML header with styles."""
    # ...

def _generate_html_body(state: AgentState) -> str:
    """Generate main report content."""
    # ...
```

---

## 4. Architecture & Design

### 4.1 Strengths ✅

1. **Excellent LangGraph Usage**
   - Clean state management with `AgentState` TypedDict
   - Proper conditional routing with `route_research()` and `route_chat()`
   - Self-correction loop with evaluation node

2. **Good Separation of Concerns**
   - Tools organized by functionality (research, synthesis, reporting)
   - Clear node responsibilities
   - Modular design allows easy extension

3. **Robust Configuration**
   - Pydantic settings for validation
   - Environment-based configuration
   - Sensible defaults

### 4.2 Improvement Opportunities

#### 4.2.1 Add Dependency Injection

**Current:**
```python
# Hard dependency on ChatOllama
llm = ChatOllama(
    base_url=ollama_base_url,
    model=ollama_model,
    temperature=0.1
)
```

**Recommended:**
```python
# src/llm_factory.py
class LLMFactory:
    @staticmethod
    def create_llm(provider: str = "ollama", **kwargs):
        if provider == "ollama":
            return ChatOllama(**kwargs)
        elif provider == "openai":
            return ChatOpenAI(**kwargs)
        # ... more providers

# Usage:
llm = LLMFactory.create_llm(
    provider=settings.llm_provider,
    model=settings.ollama_model
)
```

#### 4.2.2 Add Circuit Breaker Pattern

For external API calls, implement circuit breaker to prevent cascading failures:

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
def call_tavily_api(query: str) -> List[dict]:
    """Call Tavily with circuit breaker protection."""
    # ... implementation
```

#### 4.2.3 Add Observability

**Recommendation:** Add structured logging and metrics:

```python
# src/observability.py
import structlog

logger = structlog.get_logger()

def log_research_event(event_type: str, **kwargs):
    logger.info(
        event_type,
        **kwargs,
        timestamp=datetime.now().isoformat()
    )

# Usage:
log_research_event(
    "research_started",
    topic=topic,
    sources=selected_sources,
    depth=research_depth
)
```

---

## 5. Testing Issues

### 5.1 Test Coverage

**Current Status:** 0% (all tests failing due to import issues)

**After fixing imports, recommended additions:**

```python
# tests/test_integration.py
def test_full_research_workflow():
    """End-to-end test of research workflow."""
    initial_state = {
        "topic": "Python async programming",
        "research_depth": "quick",
        "persona": "tech"
    }
    
    result = app.invoke(initial_state)
    
    assert result["report"]
    assert len(result["web_research"]) > 0
    assert result["consolidated_summary"]

# tests/test_error_handling.py
def test_handles_api_timeout():
    """Verify graceful handling of API timeouts."""
    # Mock slow API
    # Verify timeout handling
    # Verify partial results returned
```

### 5.2 Missing Test Fixtures

**Recommendation:**

```python
# tests/conftest.py
import pytest

@pytest.fixture
def mock_ollama_response():
    """Mock Ollama LLM responses."""
    return {
        "content": "Mocked research summary",
        "metadata": {"model": "qwen3:14b"}
    }

@pytest.fixture
def sample_research_state():
    """Provide a complete sample state for testing."""
    return {
        "topic": "Test Topic",
        "research_depth": "standard",
        "persona": "general",
        # ... all required fields
    }
```

---

## 6. Performance Considerations

### 6.1 Parallelization Opportunities

**Current:** Sequential source execution  
**Recommendation:** Parallel execution of independent sources

```python
# src/tools/parallel_research.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def parallel_research_node(state: AgentState) -> dict:
    """Execute multiple research sources in parallel."""
    sources = state["research_plan"]
    
    tasks = []
    for source in sources:
        if source == "web":
            tasks.append(asyncio.to_thread(search_web_node, state))
        elif source == "wiki":
            tasks.append(asyncio.to_thread(search_wiki_node, state))
        # ... more sources
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge results into state
    return merge_research_results(results)
```

### 6.2 Caching Improvements

**Current:** Basic file-based caching  
**Recommendation:** Add Redis support for distributed caching

```python
# src/cache.py
from redis import Redis
from typing import Optional

class CacheManager:
    def __init__(self, backend: str = "file"):
        self.backend = backend
        if backend == "redis":
            self.redis = Redis(host='localhost', port=6379)
    
    def get(self, key: str) -> Optional[str]:
        if self.backend == "redis":
            return self.redis.get(key)
        # ... file backend
    
    def set(self, key: str, value: str, ttl: int = 3600):
        if self.backend == "redis":
            self.redis.setex(key, ttl, value)
        # ... file backend
```

### 6.3 Database Optimization

**File:** `src/db_manager.py`

**Current Issues:**
- No connection pooling
- No indexes on frequently queried columns
- No prepared statements

**Recommendations:**

```python
# Add indexes
cursor.execute('''
CREATE INDEX IF NOT EXISTS idx_sessions_timestamp 
ON sessions(timestamp DESC)
''')

cursor.execute('''
CREATE INDEX IF NOT EXISTS idx_sessions_topic 
ON sessions(topic)
''')

# Use connection pooling
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """Provide a database connection from pool."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()
```

---

## 7. Documentation

### 7.1 Strengths ✅

- Excellent README with clear use cases
- Good inline comments in complex sections
- API documentation in `API.md`

### 7.2 Missing Documentation

1. **Architecture Decision Records (ADRs)**
   - Why LangGraph over alternatives?
   - Why Ollama as default LLM?
   - Threading vs async decision

2. **API Documentation**
   - Add OpenAPI/Swagger spec for any REST endpoints
   - Document state schema formally

3. **Deployment Guide**
   - Production deployment checklist
   - Scaling considerations
   - Monitoring setup

**Recommendation:**

```markdown
# docs/architecture/ADR-001-langgraph-selection.md

# ADR 001: Use LangGraph for Workflow Orchestration

## Status
Accepted

## Context
Need a framework to manage complex, conditional research workflows with:
- Dynamic routing based on research needs
- Self-correction loops
- State management across multiple nodes

## Decision
Use LangGraph for workflow orchestration

## Consequences
+ Excellent state management
+ Built-in conditional routing
+ Good integration with LangChain
- Learning curve for contributors
- Tied to LangChain ecosystem
```

---

## 8. Security Recommendations

### 8.1 Input Validation

**Add validation for user inputs:**

```python
# src/validators.py (expand existing)
from pydantic import BaseModel, validator, Field

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    research_depth: str = Field(default="standard")
    persona: str = Field(default="general")
    
    @validator('topic')
    def validate_topic(cls, v):
        # Prevent injection attacks
        forbidden = ['<script>', 'javascript:', 'onerror=']
        if any(f in v.lower() for f in forbidden):
            raise ValueError("Invalid characters in topic")
        return v
    
    @validator('research_depth')
    def validate_depth(cls, v):
        if v not in ['quick', 'standard', 'deep']:
            raise ValueError("Invalid research depth")
        return v
```

### 8.2 Rate Limiting

**Add rate limiting for API endpoints:**

```python
# src/middleware/rate_limit.py
from functools import wraps
from time import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.calls = defaultdict(list)
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time()
            user_id = kwargs.get('user_id', 'default')
            
            # Clean old calls
            self.calls[user_id] = [
                t for t in self.calls[user_id] 
                if now - t < self.period
            ]
            
            if len(self.calls[user_id]) >= self.max_calls:
                raise Exception("Rate limit exceeded")
            
            self.calls[user_id].append(now)
            return func(*args, **kwargs)
        return wrapper

# Usage:
@RateLimiter(max_calls=10, period=60)
def research_endpoint(topic: str, user_id: str):
    # ... implementation
```

### 8.3 Sanitize File Uploads

**File:** `src/app.py` (lines 100-110)

**Current:**
```python
for uploaded_file in uploaded_files:
    with open(os.path.join(kb_path, uploaded_file.name), "wb") as f:
        f.write(uploaded_file.getbuffer())
```

**Recommendation:**
```python
import os
from pathlib import Path

ALLOWED_EXTENSIONS = {'.pdf', '.txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

for uploaded_file in uploaded_files:
    # Validate extension
    file_ext = Path(uploaded_file.name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        st.error(f"File type {file_ext} not allowed")
        continue
    
    # Validate size
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error(f"File too large: {uploaded_file.size} bytes")
        continue
    
    # Sanitize filename
    safe_name = "".join(c for c in uploaded_file.name if c.isalnum() or c in '._- ')
    safe_path = os.path.join(kb_path, safe_name)
    
    # Prevent directory traversal
    if not os.path.abspath(safe_path).startswith(os.path.abspath(kb_path)):
        st.error("Invalid file path")
        continue
    
    with open(safe_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
```

---

## 9. Deployment Recommendations

### 9.1 Docker Improvements

**File:** `docker-compose.yml`

**Current Issues:**
- Using `network_mode: "host"` is insecure
- No health checks
- No resource limits

**Recommended:**

```yaml
services:
  research-agent:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./reports:/app/reports
      - ./research_sessions.db:/app/research_sessions.db
      - ./knowledge_base:/app/knowledge_base
    ports:
      - "8501:8501"
    networks:
      - research-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama-data:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - research-net
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G

networks:
  research-net:
    driver: bridge

volumes:
  ollama-data:
```

### 9.2 Add Health Check Endpoint

```python
# src/health.py (expand existing)
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {
            "ollama": check_ollama_health(),
            "database": check_db_health()
        }
    }

def check_ollama_health() -> bool:
    """Verify Ollama is accessible."""
    try:
        # Ping Ollama
        return True
    except:
        return False
```

---

## 10. Priority Action Items

### Immediate (This Week)

1. ✅ **Fix import paths** - Blocks all testing
2. ✅ **Revoke exposed credentials** - Critical security issue
3. ✅ **Fix missing dependencies** - Blocks deployment
4. ✅ **Add .env to .gitignore** (verify it's working)

### Short Term (This Month)

5. ⚠️ Implement consistent error handling
6. ⚠️ Add input validation
7. ⚠️ Fix thread safety issues
8. ⚠️ Add integration tests
9. ⚠️ Centralize configuration constants

### Medium Term (This Quarter)

10. 📋 Add circuit breaker pattern
11. 📋 Implement parallel research execution
12. 📋 Add Redis caching support
13. 📋 Improve Docker configuration
14. 📋 Add comprehensive logging/observability

### Long Term (Future)

15. 🔮 Add API rate limiting
16. 🔮 Implement user authentication
17. 🔮 Add multi-tenancy support
18. 🔮 Create admin dashboard
19. 🔮 Add research analytics

---

## 11. Positive Highlights 🌟

1. **Excellent Documentation** - README is comprehensive and user-friendly
2. **Modern Stack** - LangGraph, Pydantic, Streamlit are all solid choices
3. **Feature Rich** - Multi-source research, personas, RAG support
4. **Good Testing Intent** - Test structure is there, just needs fixes
5. **Docker Support** - Makes deployment easier
6. **Thoughtful UX** - Streamlit dashboard is well-designed
7. **Self-Correction Loop** - Evaluation node is a smart addition
8. **Multilingual Support** - Query expansion is a nice touch

---

## 12. Conclusion

The Research-Agent is a **solid foundation** with excellent architecture and features. The main issues are:

1. **Import path inconsistencies** (critical, easy fix)
2. **Security concerns** (critical, requires immediate action)
3. **Code quality improvements** (medium priority, ongoing)

Once the critical issues are resolved, this will be a production-ready research automation tool.

**Estimated Effort to Production-Ready:**
- Critical fixes: 4-8 hours
- High priority improvements: 2-3 days
- Full hardening: 1-2 weeks

**Recommended Next Steps:**
1. Fix imports and run tests
2. Revoke and rotate all credentials
3. Add input validation
4. Implement proper error handling
5. Add monitoring/observability

---

## Appendix A: Quick Fix Script

```bash
#!/bin/bash
# quick_fixes.sh - Apply critical fixes

echo "🔧 Applying critical fixes..."

# 1. Fix imports in src/agent.py
sed -i 's/from tools\./from .tools./g' src/agent.py
sed -i 's/from db_manager/from .db_manager/g' src/agent.py

# 2. Fix imports in all tool files
find src/tools -name "*.py" -exec sed -i 's/from state/from ..state/g' {} \;
find src/tools -name "*.py" -exec sed -i 's/from utils/from ..utils/g' {} \;
find src/tools -name "*.py" -exec sed -i 's/from config/from ..config/g' {} \;
find src/tools -name "*.py" -exec sed -i 's/from tools\./from ./g' {} \;

# 3. Add missing dependencies
echo "python-docx>=0.8.11" >> requirements.txt

# 4. Remove duplicate PyPDF2 entry
sed -i '/^pypdf2$/d' requirements.txt

# 5. Run tests
python3 -m pytest tests/ -v

echo "✅ Fixes applied! Review the changes before committing."
```

---

**End of Code Review**
