import pytest
from unittest.mock import MagicMock, patch
from src.tools.youtube_tools import search_videos_node, summarize_videos_node

@patch("src.tools.youtube_tools.YoutubeSearch")
def test_search_videos_node(mock_yt_search, mock_agent_state):
    mock_instance = mock_yt_search.return_value
    mock_instance.to_dict.return_value = [
        {"id": "video123", "title": "Video 1", "channel": "Channel 1"}
    ]
    
    result = search_videos_node(mock_agent_state)
    
    assert "video_urls" in result
    assert "video_metadata" in result
    assert len(result["video_urls"]) == 1
    assert "video123" in result["video_urls"][0]

@patch("src.tools.youtube_tools.load_summarize_chain")
@patch("src.tools.youtube_tools.YoutubeLoader")
def test_summarize_videos_node_with_transcript(mock_loader, mock_chain, mock_agent_state):
    # Mock Chain
    mock_chain_instance = mock_chain.return_value
    mock_chain_instance.run.return_value = "Video Summary"
    
    # Mock Loader
    mock_loader_instance = mock_loader.from_youtube_url.return_value
    mock_doc = MagicMock()
    mock_doc.page_content = "Transcript content"
    mock_loader_instance.load.return_value = [mock_doc]
    
    mock_agent_state["video_urls"] = ["https://youtube.com/watch?v=1"]
    mock_agent_state["video_metadata"] = [{"title": "Video 1"}]
    
    result = summarize_videos_node(mock_agent_state)
    
    assert "summaries" in result
    assert result["summaries"][0] == "Video Summary"

@patch("src.tools.youtube_tools.load_summarize_chain")
@patch("src.tools.youtube_tools.ChatOllama")
@patch("src.tools.youtube_tools.YoutubeLoader")
def test_summarize_videos_node_fallback(mock_loader, mock_chat_ollama, mock_chain, mock_agent_state):
    # Mock LLM (for the fallback call later)
    mock_llm = mock_chat_ollama.return_value
    mock_response = MagicMock()
    mock_response.content = "Metadata Summary"
    mock_llm.invoke.return_value = mock_response
    
    # Mock Chain to load successfully (not used in fallback but loaded before)
    mock_chain.return_value = MagicMock()
    
    # Mock Loader to fail (transcript blocked)
    mock_loader.from_youtube_url.side_effect = Exception("Blocked")
    
    mock_agent_state["video_urls"] = ["https://youtube.com/watch?v=1"]
    mock_agent_state["video_metadata"] = [{"title": "Video 1", "author": "User"}]
    
    result = summarize_videos_node(mock_agent_state)
    
    assert "summaries" in result
    assert result["summaries"][0] == "Metadata Summary"
