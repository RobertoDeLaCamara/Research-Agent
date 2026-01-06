import pytest
from typing import List, Dict
from langchain_core.messages import BaseMessage

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
        "consolidated_summary": "",
        "bibliography": [],
        "pdf_path": "",
        "report": "",
        "messages": []
    }

@pytest.fixture
def mock_tavily_results():
    return [
        {"title": "Result 1", "url": "http://example.com/1", "content": "Content 1"},
        {"title": "Result 2", "url": "http://example.com/2", "content": "Content 2"}
    ]

@pytest.fixture
def mock_wiki_results():
    return [
        {"title": "Wiki Page", "summary": "Full summary", "url": "http://wiki.com"}
    ]
