import pytest

# Opt-in feature switches that a developer's .env may set. mcp_server loads .env into
# os.environ at import time, so without this they leak into every test in the session.
_OPT_IN_ENV = ("RAG_MODE", "RAG_TOP_K", "RERANK_URL", "BOOKS_RAG_URL", "USE_RAG_DEFAULT", "SEARXNG_URL", "LIGHT_LLM_MODEL", "LIGHT_LLM_BASE_URL")


@pytest.fixture(autouse=True)
def _isolate_opt_in_env(monkeypatch, tmp_path):
    """Each test starts with the opt-in switches unset; tests enable them with monkeypatch.setenv."""
    for name in _OPT_IN_ENV:
        monkeypatch.delenv(name, raising=False)
    # Prevent unit tests (e.g. generate_report_node) from writing "Test Topic" into production DB
    test_db = str(tmp_path / "pytest_sessions.db")
    monkeypatch.setattr("src.config.settings.db_path", test_db, raising=False)
    monkeypatch.setattr("src.db_manager.DB_PATH", test_db, raising=False)
    monkeypatch.setattr("src.tools.router_tools._SESSION_MEMORY_DIR", str(tmp_path / "session_memory"), raising=False)
    monkeypatch.setattr("src.tools.router_tools._MEMORY_COLLECTION", None, raising=False)

@pytest.fixture
def mock_agent_state():
    """
    Returns a sample AgentState for testing.
    """
    return {
        "topic": "Test Topic",
        "video_urls": [],
        "video_metadata": [],
        "summaries": [],
        "web_research": [],
        "wiki_research": [],
        "arxiv_research": [],
        "github_research": [],
        "scholar_research": [],
        "hn_research": [],
        "so_research": [],
        "reddit_research": [],
        "consolidated_summary": "",
        "bibliography": [],
        "pdf_path": "",
        "report": "",
        "messages": [],
        "research_plan": [],
        "next_node": "",
        "iteration_count": 0
    }

@pytest.fixture
def mock_web_results():
    return [
        {"title": "Result 1", "url": "http://example.com/1", "content": "Content 1"},
        {"title": "Result 2", "url": "http://example.com/2", "content": "Content 2"}
    ]

@pytest.fixture
def mock_wiki_results():
    return [
        {"title": "Wiki Page", "summary": "Full summary", "url": "http://wiki.com"}
    ]
