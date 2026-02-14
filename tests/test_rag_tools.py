import pytest
import os
from unittest.mock import patch, MagicMock
from src.tools.rag_tools import local_rag_node

def test_local_rag_node_no_kb(mock_agent_state):
    # Test when knowledge_base doesn't exist (it should be created but return empty)
    with patch("os.path.exists", return_value=False), \
         patch("os.makedirs") as mock_makedirs, \
         patch("sqlite3.connect") as mock_sqlite:
        result = local_rag_node(mock_agent_state)
        assert result["local_research"] == []
        mock_makedirs.assert_called_once_with("./knowledge_base")

def test_local_rag_node_with_files(mock_agent_state):
    # Mocking files in knowledge_base
    mock_files = ["test.txt", "doc.pdf"]
    mock_agent_state["topic"] = "blockchain"
    
    # helper for os.path.exists side_effect (for knowledge_base check)
    def exists_side_effect(path):
        if path == "./knowledge_base":
            return True
        return False # e.g. status file check?

    # We now use os.walk and cache
    with patch("os.path.exists", side_effect=exists_side_effect), \
         patch("os.walk", return_value=[("./knowledge_base", [], mock_files)]), \
         patch("builtins.open", MagicMock()) as mock_builtin_open, \
         patch("src.tools.rag_tools.pypdf.PdfReader") as mock_pdf, \
         patch("os.stat") as mock_stat, \
         patch("json.dump") as mock_json_dump, \
         patch("sqlite3.connect") as mock_sqlite:

        mock_stat.return_value.st_mtime = 12345
        mock_stat.return_value.st_size = 100
        
        # Setup Sqlite Mock
        mock_conn = MagicMock()
        mock_sqlite.return_value.__enter__.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # 1. init_db calls
        # 2. Cache check: SELECT path, hash FROM files
        # 3. Search: SELECT path, text FROM content
        
        # We want to simulate CACHE MISS for files, so step 2 returns empty dict
        # We want search to populate results? 
        # Actually search iterates DB content. If we insert data, does it read back from mock?
        # No, mocks don't store state unless configured.
        
        # The code separates:
        # A. Processing (Thread Pool) -> returns 'new_data' -> INSERTS into DB
        # B. Retrieval -> SELECT FROM content
        
        # So for B to return results, we must mock the return value of the SELECT query.
        # But wait, step A puts data into a list 'new_data' logic, and assumes DB insert works.
        # Step B reads from DB.
        
        # If we want the function to return results, we must ensure the final SELECT returns rows.
        # The final query is "SELECT path, text FROM content".
        # We simulate that the DB *now* has the content (either from previous inserts or magic).
        
        mock_cursor.fetchall.side_effect = [
            [], # 1. Cache Check (empty = all misses)
            # 2. Search is an iteration over cursor usually?
            # Code: for path, content in cursor:
        ]
        
        # For the iteration in Search block:
        # cursor = conn.cursor() -> execute -> iterator
        # We need to set the iterator (return value of execute, or cursor itself if iterated)
        # The code does: cursor.execute(...) -> for path, content in cursor:
        
        # So we configure the cursor instance returned by the Search connection to yield data.
        # Issue: `mock_conn.cursor()` returns the SAME mock object by default unless side_effect configured.
        # Let's verify queries.
        
        # To make it robust:
        # We can just check that ThreadPool was called (processing happened)
        # AND that the search query yielded expected results.
        
        search_results_data = [
            ("./knowledge_base/test.txt", "Blockchain technology is revolutionary."),
            ("./knowledge_base/doc.pdf", "This is a blockchain document.")
        ]
        
        # We can use side_effect on execute to detect which query is running? 
        # Or just assign `__iter__` to return data for the FINAL usage.
        # But the FIRST usage (fetchall) needs to be empty.
        
        # Let's make cursor.execute return self, and self.fetchall return empty.
        # And self.__iter__ return search_results_data.
        # But wait, cache check uses `fetchall()`, search uses iter.
        # Perfect!
        
        mock_cursor.fetchall.return_value = [] # Cache miss
        mock_cursor.__iter__.return_value = search_results_data # Search hit
        
        # Setup PDF mock
        mock_p = MagicMock()
        mock_p.pages = [MagicMock()]
        mock_p.pages[0].extract_text.return_value = "This is a blockchain document."
        mock_pdf.return_value = mock_p

        # Setup File Read
        mock_file_handle = mock_builtin_open.return_value.__enter__.return_value
        mock_file_handle.read.return_value = "Blockchain technology is revolutionary."
        
        result = local_rag_node(mock_agent_state)
        
        print(f"DEBUG RESULT: {result}")
        
        # Verify
        titles = [r["title"] for r in result["local_research"]]
        assert len(result["local_research"]) == 2, f"Got: {result['local_rag']}"
        assert "test.txt" in titles
        assert "doc.pdf" in titles
