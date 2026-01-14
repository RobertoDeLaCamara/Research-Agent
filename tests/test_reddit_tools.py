import pytest
from unittest.mock import MagicMock, patch
import os
import sys
from src.tools.reddit_tools import search_reddit_node

def test_search_reddit_node_tavily(mock_agent_state):
    """Test Reddit search with Tavily (mocked)."""
    # Mock the TavilyClient import and usage
    mock_tavily_module = MagicMock()
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [{"content": "Reddit content", "url": "reddit.com/r/test", "title": "Test Thread"}]
    }
    mock_tavily_module.TavilyClient.return_value = mock_client
    
    with patch.dict('sys.modules', {'tavily': mock_tavily_module}), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        
        # Run node
        result = search_reddit_node(mock_agent_state)
        
        # Verify
        assert "reddit_research" in result
        assert len(result["reddit_research"]) == 1
        assert result["reddit_research"][0]["content"] == "Reddit content"
        assert "next_node" in result
        assert len(result["reddit_research"]) == 1
        assert result["reddit_research"][0]["content"] == "Reddit content"
        assert "next_node" in result

def test_search_reddit_node_fallback(mock_agent_state):
    # Simulate no Tavily key and mock DDG
    with patch("src.config.settings") as mock_settings, \
         patch("os.getenv") as mock_env, \
         patch("langchain_community.tools.DuckDuckGoSearchRun") as mock_ddg:
        
        mock_settings.tavily_api_key = None
        mock_env.return_value = None # Ensure TAVILY_API_KEY is None
        
        mock_search = mock_ddg.return_value
        mock_search.run.return_value = "DDG Reddit content"
        
        result = search_reddit_node(mock_agent_state)
        
        assert len(result["reddit_research"]) == 1
        assert "DDG Reddit content" in result["reddit_research"][0]["content"]
