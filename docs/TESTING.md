# Testing Guide

## Overview

The suite runs in CI on every push to `main` (Jenkins), where the build fails below 60% line coverage of `src/`. This guide explains how to run tests, write new tests, and maintain test quality.

## Running Tests

### Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_research_tools.py -v

# Run specific test
pytest tests/test_research_tools.py::test_search_web_node_replaces_snippets_with_page_text -v
```

### Test Options

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Parallel execution
pytest -n auto
```

## Test Structure

### Current Test Suite

```
tests/
├── conftest.py                  # Shared fixtures
├── test_agent.py                # Workflow & graph tests (6 tests)
├── test_app_keys.py             # Streamlit widget keys (3 tests)
├── test_books_rag_defaults.py   # Books library defaults, USE_RAG_DEFAULT (7 tests)
├── test_chat_tools.py           # Interactive chat (2 tests)
├── test_config.py               # Settings (1 test)
├── test_credentials.py          # Per-visitor keys and model (7 tests)
├── test_llm_tiers.py            # LLM factory, light/heavy tiers, OpenAI kwargs (8 tests)
├── test_load.py                 # Concurrent load (1 test)
├── test_mcp_server.py           # MCP server: tools, jobs, export sandbox (16 tests)
├── test_persistence.py          # Database (4 tests)
├── test_rag_hybrid_mode.py      # Hybrid local_rag, books filtering (12 tests)
├── test_rag_index.py            # Indexer CLI (11 tests)
├── test_rag_tools.py            # Local knowledge, legacy mode (3 tests)
├── test_reddit_tools.py         # Reddit search and relevance filter (5 tests)
├── test_reporting_tools.py      # Export generation (8 tests)
├── test_reranker.py             # Cross-encoder rerank client (6 tests)
├── test_research_tools.py       # Research sources (13 tests)
├── test_resilience.py           # Timeouts & retries (4 tests)
├── test_router_tools.py         # Planning/routing, fact-check (5 tests)
├── test_security.py             # Input validation & XSS (7 tests)
├── test_source_loaders.py       # DuckDuckGo/Wikipedia loaders, bot-block detection (27 tests)
├── test_synthesis_tools.py      # Consolidation, truncation handling, context cap (21 tests)
├── test_uploads.py              # Upload size/type limits, path sanitising (11 tests)
├── test_vector_store.py         # ChromaDB + FTS5 store (38 tests)
└── test_youtube_tools.py        # Video summaries (3 tests)

Total: 229 tests (all passing). Counts drift as tests are added: `pytest --co -q` is the source of truth.
```

## Writing Tests

### Test Template

```python
import pytest
from unittest.mock import patch, MagicMock
from src.tools.research_tools import search_web_node

def test_search_web_node_success():
    """Test successful web search."""
    # Arrange
    state = {
        "topic": "test topic",
        "research_depth": "standard",
        "queries": {}
    }
    
    # Act
    with patch('src.tools.research_tools.duckduckgo_search') as mock_ddg:
        mock_ddg.return_value = [
            {"url": "https://example.com", "content": "Test content"}
        ]
        result = search_web_node(state)
    
    # Assert
    assert "web_research" in result
    assert len(result["web_research"]) > 0
    assert result["web_research"][0]["url"] == "https://example.com"
```

### Mocking External APIs

**Web search (DuckDuckGo):**
```python
@patch('src.tools.research_tools.duckduckgo_search')
def test_with_web_search(mock_ddg):
    mock_ddg.return_value = [
        {"url": "https://example.com", "content": "Result"}
    ]
    # ... test code
```

**LLM (any backend):** patch the factory, not a client class.
```python
@patch('src.tools.synthesis_tools.get_llm')
def test_with_llm(mock_get_llm):
    mock_response = MagicMock()
    mock_response.content = "Mocked LLM response"
    mock_get_llm.return_value.invoke.return_value = mock_response
    # ... test code
```

**Wikipedia:**
```python
@patch('src.tools.research_tools.wikipedia_pages')
def test_with_wikipedia(mock_wiki):
    mock_wiki.return_value = [
        {"title": "Test", "content": "Wiki content", "url": "https://en.wikipedia.org/wiki/Test"}
    ]
    # ... test code
```

### Testing Error Handling

```python
def test_handles_api_failure():
    """Test graceful handling of API failures."""
    state = {"topic": "test", "research_depth": "standard", "queries": {}}
    
    with patch('src.tools.research_tools.duckduckgo_search') as mock_ddg:
        mock_ddg.side_effect = Exception("API Error")
        result = search_web_node(state)
    
    # Should return empty results, not crash
    assert result["web_research"] == []
    assert "next_node" in result
```

### Testing Timeouts

```python
import time

def test_timeout_handling():
    """Test that timeouts are handled correctly."""
    state = {"topic": "test", "research_depth": "standard", "queries": {}}
    
    def slow_function(*args, **kwargs):
        time.sleep(100)  # Simulate slow API
        return []
    
    with patch('src.tools.research_tools.duckduckgo_search') as mock_ddg:
        mock_ddg.side_effect = slow_function
        
        start = time.time()
        result = search_web_node(state)
        duration = time.time() - start
        
        # Should timeout and return quickly
        assert duration < 50  # Less than timeout + buffer
        assert result["web_research"] == []
```

## Test Fixtures

### Shared Fixtures (`conftest.py`)

```python
import pytest

@pytest.fixture
def sample_state():
    """Provide a complete sample state for testing."""
    return {
        "topic": "Test Topic",
        "original_topic": "Test Topic",
        "research_depth": "standard",
        "persona": "general",
        "video_urls": [],
        "video_metadata": [],
        "summaries": [],
        "web_research": [],
        "wiki_research": [],
        "arxiv_research": [],
        "github_research": [],
        "scholar_research": [],
        "hn_research": [],
        "so_research": [],
        "reddit_research": [],
        "local_research": [],
        "consolidated_summary": "",
        "bibliography": [],
        "pdf_path": "",
        "report": "",
        "messages": [],
        "research_plan": [],
        "next_node": "",
        "iteration_count": 0,
        "last_email_hash": "",
        "evaluation_report": "",
        "queries": {},
        "source_metadata": {}
    }

@pytest.fixture
def mock_ollama_response():
    """Mock Ollama LLM response."""
    mock = MagicMock()
    mock.content = "Mocked research summary"
    return mock
```

## Integration Tests

### Full Workflow Test

```python
def test_full_research_workflow(sample_state):
    """Test complete research workflow end-to-end."""
    from src.agent import app
    
    initial_state = sample_state.copy()
    initial_state["topic"] = "Python async programming"
    initial_state["research_depth"] = "quick"
    
    # Mock all external services
    with patch('src.tools.research_tools.duckduckgo_search'), \
         patch('src.tools.synthesis_tools.get_llm'), \
         patch('src.tools.router_tools.get_llm'):
        
        result = app.invoke(initial_state)
        
        # Verify workflow completed
        assert result["report"]
        assert result["consolidated_summary"]
        assert len(result["web_research"]) > 0
```

## Test Coverage Goals

### Current Coverage
Measured with `pytest tests/ --cov=src` (229 tests): **71% of `src/`** overall. CI fails the build below 60%.

| Area | Coverage |
|------|----------|
| `llm.py`, `config.py`, `credentials.py`, `uploads.py`, `reranker.py` | 96-100% |
| `source_loaders.py`, `rag_tools.py`, `rag_index.py`, `reddit_tools.py`, `chat_tools.py` | 91-99% |
| `research_tools.py`, `vector_store.py`, `db_manager.py`, `youtube_tools.py` | 81-85% |
| `router_tools.py`, `synthesis_tools.py`, `parallel_tools.py` | 63-73% |
| `reporting_tools.py` | 54% |
| `app.py` (Streamlit UI) | 46% |
| `main.py`, `health.py`, `metrics.py` | 0% |

The figures change with every commit; rerun the command above for current numbers.

### Coverage Report

```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Performance Testing

### Load Testing

```python
import concurrent.futures

def test_concurrent_requests():
    """Test system handles multiple simultaneous requests."""
    topics = ["AI", "Python", "Docker", "LangChain", "Testing"]
    
    def run_research(topic):
        state = {"topic": topic, "research_depth": "quick"}
        return app.invoke(state)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_research, topic) for topic in topics]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All should complete successfully
    assert len(results) == 5
    assert all(r["report"] for r in results)
```

### Benchmark Tests

```python
import time

def test_research_performance():
    """Benchmark research speed."""
    state = {"topic": "test", "research_depth": "quick"}
    
    start = time.time()
    result = search_web_node(state)
    duration = time.time() - start
    
    # Should complete within timeout
    assert duration < 50
    print(f"Research completed in {duration:.2f}s")
```

## Security Testing

### Input Validation Tests

```python
def test_rejects_xss_attempts():
    """Test XSS prevention in topic validation."""
    from src.validators import validate_topic
    
    malicious_inputs = [
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "<iframe src='evil.com'>",
        "<?php system('ls'); ?>"
    ]
    
    for malicious in malicious_inputs:
        result = validate_topic(malicious)
        # Should strip dangerous characters
        assert "<" not in result
        assert ">" not in result
        assert "script" not in result.lower() or len(result) < 10
```

### File Upload Tests

```python
def test_file_upload_validation():
    """Test file upload security."""
    from src.validators import validate_file_upload
    
    # Valid file
    valid, msg = validate_file_upload("document.pdf", 1024 * 1024)
    assert valid
    
    # Invalid extension
    valid, msg = validate_file_upload("malware.exe", 1024)
    assert not valid
    assert "not allowed" in msg
    
    # Too large
    valid, msg = validate_file_upload("huge.pdf", 100 * 1024 * 1024)
    assert not valid
    assert "too large" in msg
```

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Debugging Tests

### Print Debug Info

```python
def test_with_debug():
    """Test with debug output."""
    state = {"topic": "test"}
    result = search_web_node(state)
    
    print(f"Result keys: {result.keys()}")
    print(f"Research count: {len(result['web_research'])}")
    
    assert result["web_research"]
```

### Use pytest debugger

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger at start of test
pytest --trace
```

### Capture logs

```python
import logging

def test_with_logs(caplog):
    """Test with log capture."""
    caplog.set_level(logging.INFO)
    
    result = search_web_node(state)
    
    # Check logs
    assert "Starting web search" in caplog.text
```

## Best Practices

### Test Naming
- Use descriptive names: `test_search_web_node_keeps_snippet_when_page_fetch_fails`
- Follow pattern: `test_<function>_<scenario>_<expected_result>`

### Test Organization
- One test file per source file
- Group related tests in classes
- Use fixtures for common setup

### Test Independence
- Each test should be independent
- Don't rely on test execution order
- Clean up after tests (use fixtures)

### Mocking Strategy
- Mock external services (APIs, databases)
- Don't mock code under test
- Use realistic mock data

### Assertions
- Test one thing per test
- Use specific assertions
- Include helpful error messages

## Troubleshooting

### Tests Failing Locally

```bash
# Clear pytest cache
rm -rf .pytest_cache

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python version
python --version  # Should be 3.12+
```

### Import Errors

```bash
# Ensure src is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use pytest with src path
pytest tests/ --import-mode=importlib
```

### Mock Not Working

```python
# Ensure correct import path
# If code uses: from src.tools import research_tools
# Mock should be: @patch('src.tools.research_tools.duckduckgo_search')

# If code uses: from tools import research_tools
# Mock should be: @patch('tools.research_tools.duckduckgo_search')
```

## Test Checklist

### Before Committing
- [ ] All tests pass locally
- [ ] New code has tests
- [ ] Coverage maintained/improved
- [ ] No print statements (use logging)
- [ ] Mocks are appropriate

### Code Review
- [ ] Tests are clear and readable
- [ ] Edge cases covered
- [ ] Error handling tested
- [ ] Performance acceptable
- [ ] Security considerations tested

---

**Last Updated:** February 14, 2026
**Test Count:** 67 tests (all passing)
