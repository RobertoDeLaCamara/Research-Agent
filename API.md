# API Reference

## Core Components

### Configuration (`src/config.py`)
Centralized configuration management using Pydantic.

```python
from config import settings

# Access configuration
print(settings.ollama_base_url)
print(settings.max_results_per_source)
```

### Caching (`src/cache.py`)
Intelligent caching system for research results.

```python
from cache import cache_research

@cache_research("web")
def my_research_function(topic):
    # Function will be cached automatically
    return results
```

### Progress Tracking (`src/progress.py`)
Real-time progress updates during execution.

```python
from progress import init_progress, update_progress

init_progress(12)  # 12 total steps
update_progress("Starting research...")
```

### Metrics (`src/metrics.py`)
Performance monitoring and statistics.

```python
from metrics import metrics

@metrics.time_operation("my_operation")
def my_function():
    # Function timing will be tracked
    pass

# Get statistics
stats = metrics.get_stats()
```

### Quality Scoring (`src/quality.py`)
Content quality assessment and filtering.

```python
from quality import score_content_quality, filter_quality_content

score = score_content_quality("Research content...")
filtered_results = filter_quality_content(results, min_score=0.5)
```

### Validation (`src/validators.py`)
Input validation and sanitization.

```python
from validators import validate_topic, sanitize_content

topic = validate_topic(user_input)
clean_content = sanitize_content(raw_content)
```

### Health Checks (`src/health.py`)
System health monitoring.

```python
from health import check_dependencies

healthy, checks = check_dependencies()
if not healthy:
    print("Some services are unavailable")
```

## Research Tools

### Web Search (`src/tools/research_tools.py`)
```python
def search_web_node(state: AgentState) -> dict:
    """Search the web using Tavily or DuckDuckGo fallback."""
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

### Local Knowledge (RAG)
```python
def local_rag_node(state: AgentState) -> dict:
    """Analyze files in ./knowledge_base."""
    # Returns: {"local_research": [results]}
```
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
class AgentState(TypedDict):
    topic: str
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
    source_metadata: dict
```

## Configuration Options

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OLLAMA_BASE_URL` | str | "http://localhost:11434" | Ollama service URL |
| `OLLAMA_MODEL` | str | "qwen3:14b" | LLM model to use |
| `TAVILY_API_KEY` | str | None | Tavily search API key |
| `GITHUB_TOKEN` | str | None | GitHub API token |
| `LOG_LEVEL` | str | "INFO" | Logging level |
| `MAX_RESULTS_PER_SOURCE` | int | 5 | Results per research source |
| `MAX_CONCURRENT_REQUESTS` | int | 5 | Concurrent API requests |
| `CACHE_EXPIRY_HOURS` | int | 24 | Cache expiration time |
| `REQUEST_TIMEOUT` | int | 30 | API request timeout |

### Performance Tuning

```python
# High-performance configuration
MAX_RESULTS_PER_SOURCE=10
MAX_CONCURRENT_REQUESTS=10
CACHE_EXPIRY_HOURS=48
REQUEST_TIMEOUT=60

# Conservative configuration
MAX_RESULTS_PER_SOURCE=3
MAX_CONCURRENT_REQUESTS=3
CACHE_EXPIRY_HOURS=12
REQUEST_TIMEOUT=15
```

## Error Handling

### Retry Logic
```python
from utils import api_call_with_retry

@api_call_with_retry
def my_api_call():
    # Will retry up to 3 times with exponential backoff
    return api_response
```

### Health Checks
```python
from health import check_dependencies

# Check before execution
healthy, checks = check_dependencies()
if not checks['ollama']:
    raise RuntimeError("Ollama service unavailable")
```

## Monitoring

### Metrics Collection
```python
# View performance statistics
from metrics import metrics

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
pytest tests/test_research_tools.py::test_search_web_node_ddg -v

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
