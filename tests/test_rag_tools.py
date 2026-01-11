import pytest
import os
from unittest.mock import patch, MagicMock
from src.tools.rag_tools import local_rag_node

def test_local_rag_node_no_kb(mock_agent_state):
    # Test when knowledge_base doesn't exist (it should be created but return empty)
    with patch("os.path.exists", return_value=False), \
         patch("os.makedirs") as mock_makedirs:
        result = local_rag_node(mock_agent_state)
        assert result["local_research"] == []
        mock_makedirs.assert_called_once_with("./knowledge_base")

def test_local_rag_node_with_files(mock_agent_state):
    # Mocking files in knowledge_base
    mock_files = ["test.txt", "doc.pdf"]
    mock_agent_state["topic"] = "blockchain"
    
    with patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=mock_files), \
         patch("builtins.open", MagicMock()), \
         patch("PyPDF2.PdfReader") as mock_pdf:
        
        # Setup PDF mock
        mock_p = MagicMock()
        mock_p.pages = [MagicMock()]
        mock_p.pages[0].extract_text.return_value = "This is a blockchain document."
        mock_pdf.return_value = mock_p
        
        # Mocking txt read
        with patch("src.tools.rag_tools.open", create=True) as mock_open:
            mock_f = mock_open.return_value.__enter__.return_value
            mock_f.read.return_value = "Blockchain technology is revolutionary."
            
            result = local_rag_node(mock_agent_state)
            
            assert len(result["local_research"]) == 2
            assert "test.txt" in [r["title"] for r in result["local_research"]]
            assert "doc.pdf" in [r["title"] for r in result["local_research"]]
