# Developer Reference

## Core Components

### Configuration (`src/config.py`)
Centralized configuration management using Pydantic.

```python
from src.config import settings

# Access configuration
print(settings.ollama_base_url)
print(settings.web_search_timeout)
```

### Progress Tracking (`src/progress.py`)
Real-time progress updates during execution.

```python
from src.progress import init_progress, update_progress

init_progress(12)  # 12 total steps
update_progress("Starting research...")
```

### Metrics (`src/metrics.py`)
Performance monitoring and statistics.

```python
from src.metrics import metrics

@metrics.time_operation("my_operation")
def my_function():
    # Function timing will be tracked
    pass

# Get statistics
stats = metrics.get_stats()
```

### Validation (`src/validators.py`)
Input validation and sanitization.

```python
from src.validators import validate_topic, sanitize_content

topic = validate_topic(user_input)
clean_content = sanitize_content(raw_content)
```

### Health Checks (`src/health.py`)
System health monitoring.

```python
from src.health import check_dependencies

healthy, checks = check_dependencies()
if not healthy:
    print("Some services are unavailable")
```

## Research Tools

### Web Search (`src/tools/research_tools.py`)
```python
def search_web_node(state: AgentState) -> dict:
    """Search the web with DuckDuckGo (ddgs, no API key) and fetch each page through Jina Reader."""
    # Returns: {"web_research": [results]}
```

### Academic Search
```python
def search_arxiv_node(state: AgentState) -> dict:
    """Search arXiv for academic papers."""
    # Returns: {"arxiv_research": [results]}

def search_scholar_node(state: AgentState) -> dict:
    """Search Semantic Scholar for academic papers."""
    # Returns: {"scholar_research": [results]}
```

### Local Knowledge (RAG)
```python
def local_rag_node(state: AgentState) -> dict:
    """Local knowledge: the external books library (BOOKS_RAG_URL) plus ./knowledge_base
    (RAG_MODE=legacy file scan, or RAG_MODE=hybrid chunks from the Chroma + BM25 index)."""
    # Returns: {"local_research": [results]}
```

### Code Search
```python
def search_github_node(state: AgentState) -> dict:
    """Search GitHub repositories."""
    # Returns: {"github_research": [results]}
```

## Agent State

The `AgentState` is the shared data structure passed between all nodes:

```python
class AgentState(TypedDict):  # 32 fields; main ones shown, see src/state.py
    topic: str
    original_topic: str
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]
    web_research: List[dict]
    wiki_research: List[dict]
    arxiv_research: List[dict]
    github_research: List[dict]
    scholar_research: List[dict]
    hn_research: List[dict]
    so_research: List[dict]
    reddit_research: List[dict]
    local_research: List[dict]
    consolidated_summary: str
    bibliography: List[str]
    pdf_path: str
    report: str
    messages: List[BaseMessage]
    research_plan: List[str]
    next_node: str
    iteration_count: int
    persona: str
    research_depth: str
    report_language: str  # 'es' | 'en'
    evaluation_report: str
    last_email_hash: str
    queries: dict
    source_metadata: dict
    use_rag: bool
    docx_path: str
    md_path: str
```

## Configuration Options

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OLLAMA_BASE_URL` | str | "http://localhost:11434" | Ollama service URL |
| `OLLAMA_MODEL` | str | "qwen3:14b" | LLM model to use |
| `GITHUB_TOKEN` | str | None | GitHub API token |
| `LOG_LEVEL` | str | "INFO" | Logging level |
| `WEB_SEARCH_TIMEOUT` | int | 12 | Seconds to wait for the web search thread |
| `LLM_REQUEST_TIMEOUT` | int | 60 | Default LLM call timeout (synthesis uses 360) |
| `MAX_SYNTHESIS_CONTEXT_CHARS` | int | 25000 | Source text passed to the report writer |
| `LOCAL_CONTEXT_MAX_CHARS` | int | 7500 | Part of that budget for local knowledge (0 = no cap) |
| `DEEPSEEK_API_KEY` | str | None | Use api.deepseek.com (model defaults to `deepseek-chat`) |
| `OPENAI_API_KEY` | str | None | Use an OpenAI-compatible endpoint at `OLLAMA_BASE_URL` |
| `DB_PATH` | str | "research_sessions.db" | SQLite session database |
| `RAG_KB_DIR` | str | "./knowledge_base" | Local RAG directory (read via `os.getenv`, not in `Settings`) |

Results per source follow the research depth (2 / 5 / 10), and there is no result cache.

The full list of variables that are read is on the wiki Configuration page.

### Performance Tuning

- Depth (`quick` / `standard` / `deep`) sets results per source and the output token cap (4096 / 6144 / 8192).
- `WEB_SEARCH_TIMEOUT` and `LLM_REQUEST_TIMEOUT` trade patience for latency.
- `MAX_SYNTHESIS_CONTEXT_CHARS` and `SYNTHESIS_NUM_CTX` must stay consistent: the prompt has to fit the
  Ollama context window, or Ollama drops the start of the prompt (the instructions).

## Error Handling

### Retry Logic
```python
from src.utils import api_call_with_retry

def my_api_call():
    return api_response

# Retries up to 3 times with exponential backoff (tenacity)
result = api_call_with_retry(my_api_call)
```

### Health Checks
```python
from src.health import check_dependencies

# Check before execution
healthy, checks = check_dependencies()
if not checks['ollama']:
    raise RuntimeError("Ollama service unavailable")
```

## Monitoring

### Metrics Collection
```python
# View performance statistics
from src.metrics import metrics

stats = metrics.get_stats()
print(f"Average execution time: {stats['timings']['web_search']['avg']:.2f}s")
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Operation completed successfully")
logger.error("Operation failed", exc_info=True)
```

## Testing

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_research_tools.py::test_search_web_node_replaces_snippets_with_page_text -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Test Structure
```python
def test_my_function(mock_agent_state):
    """Test function behavior."""
    result = my_function(mock_agent_state)
    assert "expected_key" in result
    assert len(result["expected_key"]) > 0
```
