
import pytest
from unittest.mock import MagicMock, patch
import concurrent.futures
from src.tools.research_tools import search_web_node

@patch('src.tools.research_tools.update_next_node')
@patch('src.config.settings')
@patch('langchain_community.tools.tavily_search.TavilySearchResults')
@patch('requests.get') # Patch globally as requests is imported locally
def test_concurrent_web_searches(mock_requests_get, mock_tavily, mock_settings, mock_next_node):
    """Test running multiple web searches in parallel."""
    
    # Setup Mocks
    mock_tavily_instance = mock_tavily.return_value
    mock_tavily_instance.run.return_value = [{"url": "http://example.com", "content": "Example content"}]
    
    # Configure requests mock for Jina reader
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Example content via Jina"
    mock_requests_get.return_value = mock_response
    
    # Settings
    mock_settings.tavily_api_key = "fake_key"
    mock_settings.web_search_timeout = 5
    mock_settings.content_fetch_timeout = 2
    mock_settings.max_content_preview_chars = 100
    
    mock_next_node.return_value = "next"
    
    # Run 10 concurrent searches
    num_requests = 10
    topics = [f"Topic {i}" for i in range(num_requests)]
    
    results = []
    
    def run_single_search(topic):
        state = {
            "topic": topic,
            "queries": {"en": topic},
            "research_depth": "quick"
        }
        return search_web_node(state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_single_search, topic) for topic in topics]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    assert len(results) == num_requests
    for res in results:
        assert "web_research" in res
        assert len(res["web_research"]) > 0
        # The content is enhanced by Jina mock
        assert "via Jina" in res["web_research"][0]["content"]

