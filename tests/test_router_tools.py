from unittest.mock import MagicMock, patch
from src.tools.router_tools import plan_research_node, update_next_node

def test_update_next_node_basic(mock_agent_state):
    mock_agent_state["research_plan"] = ["wiki", "web", "arxiv"]
    
    # Test transition from wiki to web
    next_node = update_next_node(mock_agent_state, "wiki")
    assert next_node == "web"
    
    # Test transition from web to arxiv
    next_node = update_next_node(mock_agent_state, "web")
    assert next_node == "arxiv"
    
    # Test last node
    next_node = update_next_node(mock_agent_state, "arxiv")
    assert next_node == "END"
    
    # Test non-existent node
    next_node = update_next_node(mock_agent_state, "nonexistent")
    assert next_node == "END"

@patch("src.llm.get_llm")
@patch("src.tools.router_tools.get_llm")
def test_plan_research_node(mock_router_llm_func, mock_global_llm_func, mock_agent_state):
    # Both mocks return the same mock LLM object for simplicity
    mock_llm = mock_router_llm_func.return_value
    mock_global_llm_func.return_value = mock_llm
    
    mock_response = MagicMock()
    mock_response.content = '["wiki", "web"]'
    
    mock_trans_response = MagicMock()
    mock_trans_response.content = '{"en": "topic", "es": "tema"}'
    
    mock_llm.invoke.side_effect = [mock_response, mock_trans_response]
    
    result = plan_research_node(mock_agent_state)
    
    assert result["research_plan"] == ["wiki", "web"]
    assert result["next_node"] == "parallel_search"
    assert result["iteration_count"] == 0

@patch("src.llm.get_llm")
@patch("src.tools.router_tools.get_llm")
def test_plan_research_node_persona(mock_router_llm_func, mock_global_llm_func, mock_agent_state):
    mock_llm = mock_router_llm_func.return_value
    mock_global_llm_func.return_value = mock_llm
    
    mock_response = MagicMock()
    mock_response.content = '["web"]'
    
    mock_trans_response = MagicMock()
    mock_trans_response.content = '{"en": "topic", "es": "tema"}'
    
    mock_llm.invoke.side_effect = [mock_response, mock_trans_response]
    
    # Test PM persona
    mock_agent_state["persona"] = "pm"
    result = plan_research_node(mock_agent_state)
    assert result["research_plan"] == ["web"]
    assert mock_llm.invoke.called
    
    # Get the prompt from call args
    # Note: invoke was called twice, we want the first call for the persona check
    prompt = mock_llm.invoke.call_args_list[0][0][0][0].content
    assert "Product Manager" in prompt or "necesidades del usuario" in prompt


@patch("src.tools.router_tools.expand_queries_multilingual")
def test_plan_research_node_expands_queries_even_with_predefined_plan(mock_expand, mock_agent_state):
    """Regression test: when the GUI provides a predefined research_plan on iteration 0,
    plan_research_node must still populate multilingual queries so English sources don't get raw Spanish."""
    mock_expand.return_value = {
        "en": "Agentic AI in 6G networks standardization in 3GPP",
        "es": "IA agentica en redes 6G estandarización en 3GPP",
    }
    mock_agent_state["topic"] = "IA agentica en redes 6G: estado del arte, evolución y estandarización en 3gpp"
    mock_agent_state["research_plan"] = ["local_rag", "web", "arxiv"]
    mock_agent_state["iteration_count"] = 0

    result = plan_research_node(mock_agent_state)

    mock_expand.assert_called_once_with(mock_agent_state["topic"])
    assert result["queries"]["en"] == "Agentic AI in 6G networks standardization in 3GPP"
    assert result["research_plan"] == ["local_rag", "web", "arxiv"]


@patch("src.tools.router_tools.get_llm")
def test_evaluate_research_node_injects_current_date_and_sources_digest(mock_get_llm, mock_agent_state):
    """Regression test: evaluate_research_node must pass the current system date and retrieved
    source excerpts so the fact-checker does not flag current-year dates or source-backed metrics."""
    from src.tools.router_tools import evaluate_research_node
    import datetime

    mock_llm = mock_get_llm.return_value
    mock_resp = MagicMock()
    mock_resp.content = '{"dubious_claims": [], "reasoning": "Verificado con fuente 3GPP."}'
    mock_llm.invoke.return_value = mock_resp

    mock_agent_state["topic"] = "IA agentica en redes 6G"
    mock_agent_state["research_depth"] = "deep"
    mock_agent_state["consolidated_summary"] = "En marzo de 2026 se inició Release-21 con el 50% de Release-20 dedicado a 6G."
    mock_agent_state["web_research"] = [
        {
            "title": "AI and Agentic Protocols for 6G",
            "url": "https://www.3gpp.org/technologies/ai-agentic-protocols",
            "content": "3GPP decided to dedicate 50% of Release-20 time to 6G studies. Stage 1 normative work started in March 2026.",
        }
    ]

    result = evaluate_research_node(mock_agent_state)

    assert result["next_node"] == "END"
    assert "⚠️" not in result.get("consolidated_summary", mock_agent_state["consolidated_summary"])
    prompt = mock_llm.invoke.call_args[0][0][0].content
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    assert f"FECHA ACTUAL DEL SISTEMA: {today_str}" in prompt
    assert "https://www.3gpp.org/technologies/ai-agentic-protocols" in prompt
    assert "50% of Release-20" in prompt
