from unittest.mock import patch, MagicMock
from src.tools.rag_tools import local_rag_node

def test_local_rag_node_no_kb(mock_agent_state):
    # Test when knowledge_base doesn't exist (it should be created but return empty)
    with patch("os.path.exists", return_value=False), \
         patch("os.makedirs") as mock_makedirs, \
         patch("sqlite3.connect"):
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
         patch("src.tools.rag_tools.pypdf.PdfReader") as mock_pdf, \
         patch("os.stat") as mock_stat, \
         patch("json.dump"):
         
        mock_stat.return_value.st_mtime = 12345
        mock_stat.return_value.st_size = 100
        
        # Setup PDF mock
        mock_p = MagicMock()
        mock_p.pages = [MagicMock()]
        mock_p.pages[0].extract_text.return_value = "This is a blockchain document."
        mock_pdf.return_value = mock_p

        # Setup File Read
        mock_file_handle = mock_builtin_open.return_value.__enter__.return_value
        mock_file_handle.read.return_value = "Blockchain technology is revolutionary."
        
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


def test_local_rag_node_ignores_substring_stopword_matches_and_dummy_files(mock_agent_state, tmp_path, monkeypatch):
    """Regression test: Spanish stopwords like 'en' and 'y' must NOT match English words containing
    'en' ('passenger', 'document') as substrings, and dummy test files must be ignored."""
    monkeypatch.setenv("RAG_KB_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_MODE", "legacy")

    (tmp_path / "transport_concept.txt").write_text(
        "A motorized vehicle with four wheels designed for passenger transport on roads."
    )
    (tmp_path / "test_doc.txt").write_text(
        "This is a test document for RAG persistence verification."
    )
    (tmp_path / "unrelated_cooking.txt").write_text(
        "Chicken soup with green vegetables and fresh lemon juice."
    )
    (tmp_path / "3gpp_6g_notes.txt").write_text(
        "3GPP Release 20 studies agentic AI protocols for 6G mobile networks."
    )

    mock_agent_state["topic"] = "IA agentica en redes 6G: estado del arte, evolución y estandarización en 3gpp"
    result = local_rag_node(mock_agent_state)

    titles = [r["title"] for r in result["local_research"]]
    assert titles == ["3gpp_6g_notes.txt"]
