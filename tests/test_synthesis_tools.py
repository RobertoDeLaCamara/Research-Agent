import pytest
from unittest.mock import MagicMock, patch
from src.tools.synthesis_tools import _clean_truncated_tail, _was_truncated, consolidate_research_node

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
    mock_response.response_metadata = {"finish_reason": "length"}  # the model hit the token cap
    mock_llm.invoke.return_value = mock_response

    mock_agent_state["research_depth"] = "deep"
    mock_agent_state["web_research"] = [{"title": "3GPP", "url": "https://3gpp.org", "content": "6G studies"}]

    result = consolidate_research_node(mock_agent_state)

    assert mock_get_llm.call_args.kwargs["num_predict"] == 8192
    summary = result["consolidated_summary"]
    assert not summary.endswith("Esta afirm")
    assert summary.endswith("3GPP ha decidido dedicar el 50% del tiempo de Release-20 a estudios de 6G.")


# ── Truncation cleanup only runs on reports the model actually cut ─────────────────────────


COMPLETE_ENDINGS = [
    "## Ejemplo\n```python\nx = 1\n```",
    "| Algoritmo | Uso |\n|---|---|\n| CUBIC | Linux por defecto |",
    "## Referencias\n- Wikipedia: https://en.wikipedia.org/wiki/BBR",
    "| A | B |\n|---|---|\n| v. 2.0 | ver doc. oficial |",
]


@pytest.mark.parametrize("text", COMPLETE_ENDINGS)
def test_complete_reports_are_never_trimmed(text):
    assert _clean_truncated_tail(text, truncated=False) == text


@pytest.mark.parametrize("text", COMPLETE_ENDINGS[:2] + COMPLETE_ENDINGS[3:])
def test_finished_fences_and_table_rows_survive_even_when_truncated(text):
    assert _clean_truncated_tail(text, truncated=True) == text


def test_truncated_table_row_is_dropped_not_cut_mid_cell():
    text = "| A | B |\n|---|---|\n| v. 2.0 | ver doc. ofi"
    assert _clean_truncated_tail(text, truncated=True) == "| A | B |\n|---|---|"


def test_cut_inside_code_block_gets_closed():
    out = _clean_truncated_tail("## Ej\n```python\nx = 1\ny = comp", truncated=True)
    assert out.count("```") == 2


@pytest.mark.parametrize("meta,expected", [
    ({"finish_reason": "length"}, True),   # OpenAI-compatible (DeepSeek, Groq...)
    ({"done_reason": "length"}, True),     # Ollama
    ({"finish_reason": "stop"}, False),    # hit </report>
    ({"done_reason": "stop"}, False),
    ({}, False),
])
def test_was_truncated_reads_the_stop_reason(meta, expected):
    resp = MagicMock()
    resp.response_metadata = meta
    assert _was_truncated(resp) is expected


@patch("src.tools.synthesis_tools.get_llm")
def test_complete_report_ending_in_code_fence_is_kept_whole(mock_get_llm, mock_agent_state):
    """Regression: stop=["</report>"] strips the closing tag, which used to make every report look cut."""
    resp = MagicMock()
    resp.content = "<report>\n## Ejemplo\n```python\nx = 1\n```"
    resp.response_metadata = {"finish_reason": "stop"}
    mock_get_llm.return_value.invoke.return_value = resp
    mock_agent_state["web_research"] = [{"title": "t", "url": "https://x", "content": "c"}]
    out = consolidate_research_node(mock_agent_state)["consolidated_summary"]
    assert out.endswith("```") and out.count("```") == 2
