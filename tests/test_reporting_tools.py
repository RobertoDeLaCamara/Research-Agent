import pytest
from unittest.mock import MagicMock, patch
from src.tools.reporting_tools import generate_report_node

def test_generate_report_node_completely_empty(mock_agent_state):
    """Test when no information at all is found."""
    mock_agent_state["summaries"] = []
    mock_agent_state["consolidated_summary"] = ""
    mock_agent_state["wiki_research"] = []
    # has_content should be False
    result = generate_report_node(mock_agent_state)
    
    assert "report" in result
    assert "No se encontró información relevante" in result["report"]

def test_generate_report_node_only_consolidated(mock_agent_state):
    """Test when only consolidated summary is found (no videos)."""
    mock_agent_state["summaries"] = []
    mock_agent_state["consolidated_summary"] = "This is a great executive summary."
    
    result = generate_report_node(mock_agent_state)
    
    assert "report" in result
    assert "💡 Síntesis Ejecutiva Consolidada" in result["report"]
    assert "This is a great executive summary." in result["report"]
    # Should NOT have the "No se encontró" message
    assert "No se encontró información relevante" not in result["report"]

def test_generate_report_node_full(mock_agent_state):
    """Test a full report scenario."""
    mock_agent_state["summaries"] = ["Summary 1"]
    mock_agent_state["video_metadata"] = [{"title": "Video 1", "url": "http://youtube.com/1", "author": "Author 1"}]
    mock_agent_state["topic"] = "Test Topic"
    mock_agent_state["consolidated_summary"] = "Executive Summary Content"
    mock_agent_state["web_research"] = [{"content": "Web Info"}]
    mock_agent_state["wiki_research"] = [{"title": "Wiki Title", "url": "http://wiki.com", "summary": "Wiki Summary"}]
    
    result = generate_report_node(mock_agent_state)
    
    assert "report" in result
    report_html = result["report"]
    assert "Test Topic" in report_html
    assert "Executive Summary Content" in report_html
    assert "Video 1" in report_html
    assert "Wiki Title" in report_html

@patch("src.tools.reporting_tools.FPDF")
def test_generate_pdf(mock_fpdf, mock_agent_state):
    from src.tools.reporting_tools import generate_pdf
    
    mock_agent_state["consolidated_summary"] = "Test Summary"
    mock_agent_state["bibliography"] = ["Source 1", "Source 2"]
    topic = "Test Topic"
    
    generate_pdf(mock_agent_state, topic, "reporte_investigacion.pdf", ["Source 1", "Source 2"])
    
    # Assert FPDF was called
    assert mock_fpdf.called
