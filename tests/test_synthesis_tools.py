import pytest
from unittest.mock import MagicMock, patch
from src.tools.synthesis_tools import consolidate_research_node

@patch("src.tools.synthesis_tools.ChatOllama")
def test_consolidate_research_node_success(mock_chat_ollama, mock_agent_state):
    # Setup mocks
    mock_llm = mock_chat_ollama.return_value
    mock_response = MagicMock()
    mock_response.content = "This is a consolidated summary."
    mock_llm.invoke.return_value = mock_response
    
    # Populate mock state
    mock_agent_state["web_research"] = [{"content": "Web content"}]
    mock_agent_state["wiki_research"] = [{"title": "Wiki", "summary": "Wiki content"}]
    
    result = consolidate_research_node(mock_agent_state)
    
    assert "consolidated_summary" in result
    assert result["consolidated_summary"] == "This is a consolidated summary."
    assert mock_llm.invoke.called

@patch("src.tools.synthesis_tools.ChatOllama")
def test_consolidate_research_node_error(mock_chat_ollama, mock_agent_state):
    # Setup mocks to raise an error
    mock_llm = mock_chat_ollama.return_value
    mock_llm.invoke.side_effect = Exception("LLM Error")
    
    result = consolidate_research_node(mock_agent_state)
    
    assert "consolidated_summary" in result
    assert "No fue posible generar" in result["consolidated_summary"]
