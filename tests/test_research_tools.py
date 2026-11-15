from unittest.mock import MagicMock, patch
from src.tools.research_tools import search_web_node, search_wiki_node, search_arxiv_node

@patch("requests.get")
def test_search_web_node_replaces_snippets_with_page_text(mock_get, mock_agent_state):
    """Search hits come from DuckDuckGo; their content is replaced by the Jina Reader text."""
    mock_get.return_value = MagicMock(status_code=200, text="Markdown content from Jina")
    with patch("src.tools.research_tools.duckduckgo_search") as mock_ddg:
        mock_ddg.return_value = [{"url": "http://test.com", "content": "Search snippet", "title": "Hit"}]

        result = search_web_node(mock_agent_state)

    assert result["web_research"] == [
        {"url": "http://test.com", "content": "Markdown content from Jina", "title": "Hit"}
    ]
    assert mock_get.call_args.args[0] == "https://r.jina.ai/http://test.com"
    assert "next_node" in result


@patch("requests.get")
def test_search_web_node_keeps_snippet_when_page_fetch_fails(mock_get, mock_agent_state):
    mock_get.return_value = MagicMock(status_code=500)
    with patch("src.tools.research_tools.duckduckgo_search") as mock_ddg:
        mock_ddg.return_value = [{"url": "http://ddg-hit.com", "content": "From DDG", "title": "Hit"}]

        result = search_web_node(mock_agent_state)

    assert result["web_research"] == [{"url": "http://ddg-hit.com", "content": "From DDG", "title": "Hit"}]


@patch("requests.get")
def test_search_web_node_returns_nothing_when_search_fails(mock_get, mock_agent_state):
    with patch("src.tools.research_tools.duckduckgo_search", side_effect=RuntimeError("blocked")):
        result = search_web_node(mock_agent_state)

    assert result["web_research"] == []
    assert "next_node" in result
    mock_get.assert_not_called()


def test_search_wiki_node(mock_agent_state):
    with patch("src.tools.research_tools.wikipedia_pages") as mock_wiki:
        mock_wiki.return_value = [
            {"title": "Test Wiki", "content": "This is a wiki page content", "url": "http://wiki.com"}
        ]

        result = search_wiki_node(mock_agent_state)

        # The node must use the patched loader, never the real Wikipedia API.
        assert result["wiki_research"] == [
            {"title": "Test Wiki", "summary": "This is a wiki page content...", "url": "http://wiki.com"}
        ]
        assert "next_node" in result

@patch("arxiv.Client")
@patch("arxiv.Search")
def test_search_arxiv_node(mock_search_class, mock_client_class, mock_agent_state):
    mock_result = MagicMock()
    mock_result.title = "Arxiv Title"
    mock_result.summary = "Arxiv Summary"
    mock_result.entry_id = "http://arxiv.org/1"
    mock_author = MagicMock()
    mock_author.name = "Author 1"
    mock_result.authors = [mock_author]
    
    mock_client = mock_client_class.return_value
    mock_client.results.return_value = [mock_result]
    
    result = search_arxiv_node(mock_agent_state)
    
    assert "arxiv_research" in result
    assert "next_node" in result

def test_search_scholar_node(mock_agent_state):
    with patch("src.tools.research_tools.SemanticScholar") as mock_scholar_class:
        mock_instance = mock_scholar_class.return_value
        mock_paper = MagicMock()
        mock_paper.title = "Scholar Title"
        mock_paper.abstract = "Scholar Abstract"
        mock_paper.url = "http://scholar.com/1"
        mock_paper.authors = [{"name": "Author 1"}]
        mock_paper.year = 2024
        
        mock_instance.search_paper.return_value = [mock_paper]
        
        from src.tools.research_tools import search_scholar_node
        result = search_scholar_node(mock_agent_state)
        
        assert "scholar_research" in result
        assert "next_node" in result

def test_search_github_node(mock_agent_state):
    with patch("src.tools.research_tools.Github") as mock_github_class:
        mock_instance = mock_github_class.return_value
        mock_repo = MagicMock()
        mock_repo.full_name = "user/repo"
        mock_repo.description = "Repo Desc"
        mock_repo.html_url = "http://github.com/repo"
        mock_repo.stargazers_count = 100
        
        mock_repos = MagicMock()
        mock_repos.totalCount = 1
        mock_repos.__iter__.return_value = [mock_repo]
        mock_instance.search_repositories.return_value = mock_repos
        
        from src.tools.research_tools import search_github_node
        result = search_github_node(mock_agent_state)

        # The node must use the patched client, never the real GitHub API.
        mock_instance.search_repositories.assert_called()
        assert [r["name"] for r in result["github_research"]] == ["user/repo"]
        assert "next_node" in result


def test_search_github_node_passes_token_as_auth(mock_agent_state):
    with patch("src.tools.research_tools.get_credential", return_value="tok"), \
         patch("src.tools.research_tools.Auth") as mock_auth, \
         patch("src.tools.research_tools.Github") as mock_github_class:
        mock_repos = MagicMock()
        mock_repos.totalCount = 1
        mock_repos.__iter__.return_value = []
        mock_github_class.return_value.search_repositories.return_value = mock_repos

        from src.tools.research_tools import search_github_node
        search_github_node(mock_agent_state)

        mock_auth.Token.assert_called_once_with("tok")
        mock_github_class.assert_called_once_with(auth=mock_auth.Token.return_value)

@patch("requests.get")
def test_search_hn_node(mock_get, mock_agent_state):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": [{"title": "HN Story", "objectID": "123", "author": "user", "points": 10, "num_comments": 2}]
    }
    mock_get.return_value = mock_response
    
    from src.tools.research_tools import search_hn_node
    result = search_hn_node(mock_agent_state)
    
    assert "hn_research" in result
    assert "next_node" in result

def test_search_so_node(mock_agent_state):
    with patch("stackapi.StackAPI") as mock_stackapi:
        mock_instance = mock_stackapi.return_value
        mock_instance.fetch.return_value = {
            "items": [{"title": "SO Question", "link": "http://so.com/q", "score": 5, "is_answered": True, "tags": ["python"]}]
        }
        
        from src.tools.research_tools import search_so_node
        result = search_so_node(mock_agent_state)
        
        assert "so_research" in result
        assert "next_node" in result
