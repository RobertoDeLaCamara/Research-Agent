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
    
    # helper for os.path.exists side_effect
    def exists_side_effect(path):
        if "rag_cache.json" in path:
            return False
        return True

    # We now use os.walk and cache
    with patch("os.path.exists", side_effect=exists_side_effect), \
         patch("os.walk", return_value=[("./knowledge_base", [], mock_files)]), \
         patch("builtins.open", MagicMock()) as mock_builtin_open, \
         patch("src.tools.rag_tools.PyPDF2.PdfReader") as mock_pdf, \
         patch("os.stat") as mock_stat, \
         patch("json.dump") as mock_json_dump:
         
        mock_stat.return_value.st_mtime = 12345
        mock_stat.return_value.st_size = 100
        
        # Setup PDF mock
        mock_p = MagicMock()
        mock_p.pages = [MagicMock()]
        mock_p.pages[0].extract_text.return_value = "This is a blockchain document."
        mock_pdf.return_value = mock_p
        
        # Provide text content for ANY file read (TXT files use this)
        # PDF reader uses mock_pdf, so we don't care what open returns for it as long as it's a context manager
        mock_file_handle = mock_builtin_open.return_value.__enter__.return_value
        mock_file_handle.read.return_value = "Blockchain technology is revolutionary."
        
        result = local_rag_node(mock_agent_state)
        
        print(f"DEBUG RESULT: {result}") # In case of failure
        
        # Verify
        titles = [r["title"] for r in result["local_research"]]
        assert len(result["local_research"]) == 2, f"Expected 2 results, got {len(result['local_research'])}: {titles}"
        assert "test.txt" in titles
        assert "doc.pdf" in titles
