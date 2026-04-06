import pytest
from unittest.mock import MagicMock, patch
from src.tools.router_tools import plan_research_node, update_next_node, router_node

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

def test_router_node_mapping(mock_agent_state):
    mock_agent_state["research_plan"] = ["wiki", "youtube", "local_rag", "reddit"]
    
    # Test mapping for wiki
    mock_agent_state["next_node"] = "wiki"
    assert router_node(mock_agent_state) == "search_wiki"
    
    # Test mapping for youtube
    mock_agent_state["next_node"] = "youtube"
    assert router_node(mock_agent_state) == "search_videos"
    
    # Test mapping for reddit
    mock_agent_state["next_node"] = "reddit"
    assert router_node(mock_agent_state) == "search_reddit"
    
    # Test mapping for local_rag
    mock_agent_state["next_node"] = "local_rag"
    assert router_node(mock_agent_state) == "local_rag"
    
    # Test END
    mock_agent_state["next_node"] = "END"
    assert router_node(mock_agent_state) == "consolidate_research"
