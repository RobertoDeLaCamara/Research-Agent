import pytest
from unittest.mock import MagicMock, patch
from src.tools.chat_tools import chat_node
from langchain_core.messages import HumanMessage, AIMessage

def test_chat_node_basic_response(mock_agent_state):
    """Test that chat_node returns a response from the LLM."""
    mock_agent_state["topic"] = "Test Topic"
    mock_agent_state["consolidated_summary"] = "Knowledge context"
    mock_agent_state["messages"] = [HumanMessage(content="Explain this research")]
    
    with patch("src.tools.chat_tools.ChatOllama") as mock_ollama:
        mock_instance = mock_ollama.return_value
        mock_instance.invoke.return_value = AIMessage(content="Here is the explanation")
        
        result = chat_node(mock_agent_state)
        
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Here is the explanation"

def test_chat_node_suggests_research(mock_agent_state):
    """Test that chat_node can suggest more research."""
    mock_agent_state["topic"] = "Solana"
    mock_agent_state["messages"] = [HumanMessage(content="Find more about consensus")]
    
    with patch("src.tools.chat_tools.ChatOllama") as mock_ollama:
        mock_instance = mock_ollama.return_value
        mock_instance.invoke.return_value = AIMessage(content="I need more info. INVESTIGACIÓN: Consensus in Solana.")
        
        result = chat_node(mock_agent_state)
        
        assert "INVESTIGACIÓN:" in result["messages"][0].content
