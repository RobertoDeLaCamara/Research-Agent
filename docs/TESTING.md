# Testing Guide

## Overview

The Research-Agent has comprehensive test coverage with 37 passing tests. This guide explains how to run tests, write new tests, and maintain test quality.

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
pytest tests/test_research_tools.py::test_search_web_node_tavily -v
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
├── test_agent.py                # Workflow tests (5 tests)
├── test_research_tools.py       # Research sources (8 tests)
├── test_router_tools.py         # Planning/routing (4 tests)
├── test_synthesis_tools.py      # Consolidation (2 tests)
├── test_reporting_tools.py      # Export generation (4 tests)
├── test_chat_tools.py           # Interactive chat (2 tests)
├── test_rag_tools.py            # Local knowledge (2 tests)
├── test_reddit_tools.py         # Reddit search (2 tests)
├── test_youtube_tools.py        # Video summaries (3 tests)
└── test_persistence.py          # Database (5 tests)

Total: 37 tests (100% pass rate)
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
    with patch('src.tools.research_tools.TavilySearchResults') as mock_tavily:
        mock_tavily.return_value.run.return_value = [
            {"url": "https://example.com", "content": "Test content"}
        ]
        result = search_web_node(state)
    
    # Assert
    assert "web_research" in result
    assert len(result["web_research"]) > 0
    assert result["web_research"][0]["url"] == "https://example.com"
```

### Mocking External APIs

**Tavily Search:**
```python
@patch('src.tools.research_tools.TavilySearchResults')
def test_with_tavily(mock_tavily):
    mock_tavily.return_value.run.return_value = [
        {"url": "https://example.com", "content": "Result"}
    ]
    # ... test code
```

**Ollama LLM:**
```python
@patch('src.tools.synthesis_tools.ChatOllama')
def test_with_ollama(mock_ollama):
    mock_response = MagicMock()
    mock_response.content = "Mocked LLM response"
    mock_ollama.return_value.invoke.return_value = mock_response
    # ... test code
```

**Wikipedia:**
```python
@patch('src.tools.research_tools.WikipediaLoader')
def test_with_wikipedia(mock_wiki):
    mock_wiki.return_value.load.return_value = [
        MagicMock(page_content="Wiki content", metadata={"title": "Test"})
    ]
    # ... test code
```

### Testing Error Handling

```python
def test_handles_api_failure():
    """Test graceful handling of API failures."""
    state = {"topic": "test", "research_depth": "standard", "queries": {}}
    
    with patch('src.tools.research_tools.TavilySearchResults') as mock_tavily:
        mock_tavily.return_value.run.side_effect = Exception("API Error")
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
    
    with patch('src.tools.research_tools.TavilySearchResults') as mock_tavily:
        mock_tavily.return_value.run = slow_function
        
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
    with patch('src.tools.research_tools.TavilySearchResults'), \
         patch('src.tools.synthesis_tools.ChatOllama'), \
         patch('src.tools.router_tools.ChatOllama'):
        
        result = app.invoke(initial_state)
        
        # Verify workflow completed
        assert result["report"]
        assert result["consolidated_summary"]
        assert len(result["web_research"]) > 0
```

## Test Coverage Goals

### Current Coverage
- ✅ All research tools: 100%
- ✅ Router tools: 100%
- ✅ Synthesis tools: 100%
- ✅ Reporting tools: 100%
- ✅ Database operations: 100%
- ✅ Validation functions: 100%

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
- Use descriptive names: `test_search_web_node_with_tavily_api`
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
python --version  # Should be 3.10+
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
# Mock should be: @patch('src.tools.research_tools.TavilySearchResults')

# If code uses: from tools import research_tools
# Mock should be: @patch('tools.research_tools.TavilySearchResults')
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

**Last Updated:** January 20, 2026  
**Test Count:** 37 tests (100% pass rate)
