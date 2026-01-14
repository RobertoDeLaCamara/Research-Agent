import pytest
from unittest.mock import MagicMock, patch
import os
from src.tools.reddit_tools import search_reddit_node

@pytest.mark.skipif(True, reason="tavily module not installed in test environment")
def test_search_reddit_node_tavily(mock_agent_state):
    # Setup mock for TavilyClient - mock where it's imported
    with patch("tavily.TavilyClient") as mock_client_class, \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        mock_client = mock_client_class.return_value
        mock_client.search.return_value = {
            "results": [{"content": "Reddit content", "url": "reddit.com/r/test", "title": "Test Thread"}]
        }
        
        # Run node
        result = search_reddit_node(mock_agent_state)
        
        # Verify
        assert "reddit_research" in result
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
