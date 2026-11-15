from unittest.mock import MagicMock, patch
from src.tools.synthesis_tools import consolidate_research_node

@patch("src.tools.synthesis_tools.get_llm")
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

@patch("src.tools.synthesis_tools.get_llm")
def test_consolidate_research_node_persona(mock_chat_ollama, mock_agent_state):
    # Setup mocks
    mock_llm = mock_chat_ollama.return_value
    mock_response = MagicMock()
    mock_response.content = "PM style summary."
    mock_llm.invoke.return_value = mock_response
    
    # Test PM persona
    mock_agent_state["persona"] = "pm"
    mock_agent_state["local_research"] = [{"title": "Internal docs", "content": "Our strategy is..."}]
    
    result = consolidate_research_node(mock_agent_state)
    
    assert result["consolidated_summary"] == "PM style summary."
    assert mock_llm.invoke.called
    
    # Check prompt contents
    prompt = mock_chat_ollama.return_value.invoke.call_args[0][0][0].content
    assert "Product Manager" in prompt
    assert "CONOCIMIENTO LOCAL" in prompt


@patch("src.tools.synthesis_tools.get_llm")
def test_consolidate_research_node_cleans_truncated_tail_and_uses_depth_aware_tokens(mock_get_llm, mock_agent_state):
    """Regression test: deep mode must allocate >= 8192 output tokens, and if the LLM still
    truncates mid-word before </report> (e.g. 'Esta afirm'), the broken trailing fragment is trimmed."""
    mock_llm = mock_get_llm.return_value
    mock_response = MagicMock()
    mock_response.content = (
        "<report>\n"
        "## Contexto de 6G\n"
        "3GPP estudia protocolos agénticos en Release 20.\n\n"
        "## Verificación de Datos\n"
        "* **Afirmación 1**: 3GPP ha decidido dedicar el 50% del tiempo de Release-20 a estudios de 6G. Esta afirm"
    )
    mock_llm.invoke.return_value = mock_response

    mock_agent_state["research_depth"] = "deep"
    mock_agent_state["web_research"] = [{"title": "3GPP", "url": "https://3gpp.org", "content": "6G studies"}]

    result = consolidate_research_node(mock_agent_state)

    assert mock_get_llm.call_args.kwargs["num_predict"] == 8192
    summary = result["consolidated_summary"]
    assert not summary.endswith("Esta afirm")
    assert summary.endswith("3GPP ha decidido dedicar el 50% del tiempo de Release-20 a estudios de 6G.")
