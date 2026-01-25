
import pytest
from unittest.mock import MagicMock, patch
import time
from src.tools.research_tools import search_web_node, search_wiki_node
from src.utils import api_call_with_retry

def test_api_call_with_retry_success():
    """Test that it returns result immediately on success."""
    mock_func = MagicMock(return_value="Success")
    result = api_call_with_retry(mock_func)
    assert result == "Success"
    assert mock_func.call_count == 1

def test_api_call_with_retry_failure_then_success():
    """Test that it retries on failure."""
    mock_func = MagicMock(side_effect=[ValueError("Fail"), "Success"])
    result = api_call_with_retry(mock_func, max_retries=3, delay=0.01)
    assert result == "Success"
    assert mock_func.call_count == 2

from tenacity import RetryError

def test_api_call_with_retry_max_retries():
    """Test that it raises RetryError (or original) after max retries."""
    mock_func = MagicMock(side_effect=ValueError("Fail"))
    
    # Tenacity raises RetryError by default unless configured otherwise
    with pytest.raises(RetryError):
        api_call_with_retry(mock_func) # using default settings or pass kwargs if accepted
        
    # check call count: initial + 3 retries = 4
    # The default in utils.py is stop_after_attempt(3) -> 3 calls total
    assert mock_func.call_count == 3

@patch('src.tools.research_tools.update_next_node')
@patch('src.config.settings') # Patch the instantiated object in config module
def test_search_web_node_timeout(mock_settings, mock_next_node):
    """Test that search_web_node returns graceful empty result on timeout."""
    
    # Setup state
    state = {
        "topic": "Integration Testing",
        "queries": {"en": "Integration Testing"},
        "research_depth": "quick"
    }
    
    mock_next_node.return_value = "next_step"
    
    # Configure mock settings object
    mock_settings.tavily_api_key = "fake_key"
    mock_settings.web_search_timeout = 0.1 # Very short timeout
    mock_settings.content_fetch_timeout = 0.1
    mock_settings.max_content_preview_chars = 100
    
    # Mock TavilySearchResults to hang
    with patch('langchain_community.tools.tavily_search.TavilySearchResults') as MockTavily:
        mock_tavily_instance = MockTavily.return_value
        
        def slow_run(*args, **kwargs):
            time.sleep(0.5) # Sleep longer than timeout
            return [{"url": "http://slow.com", "content": "Too slow"}]
        
        mock_tavily_instance.run.side_effect = slow_run
        
        # Configure logging to verify timeout warning
        with patch('src.tools.research_tools.logger') as mock_logger:
            result = search_web_node(state)
            
            assert "web_research" in result
            assert result["web_research"] == [] # Should be empty due to timeout behavior

