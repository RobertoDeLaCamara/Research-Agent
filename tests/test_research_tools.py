from unittest.mock import MagicMock, patch
from src.tools.research_tools import search_web_node, search_wiki_node, search_arxiv_node

@patch("requests.get")
def test_search_web_node_replaces_snippets_with_page_text(mock_get, mock_agent_state):
    """Search hits come from DuckDuckGo; their content is replaced by the Jina Reader text."""
    mock_get.return_value = MagicMock(status_code=200, text="Markdown content from Jina")
    with patch("src.tools.research_tools.web_search") as mock_ddg:
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
    with patch("src.tools.research_tools.web_search") as mock_ddg:
        mock_ddg.return_value = [{"url": "http://ddg-hit.com", "content": "From DDG", "title": "Hit"}]

        result = search_web_node(mock_agent_state)

    assert result["web_research"] == [{"url": "http://ddg-hit.com", "content": "From DDG", "title": "Hit"}]


@patch("requests.get")
def test_search_web_node_returns_nothing_when_search_fails(mock_get, mock_agent_state):
    with patch("src.tools.research_tools.web_search", side_effect=RuntimeError("blocked")):
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


@patch("requests.get")
def test_search_web_node_keeps_ddg_snippet_when_jina_returns_cloudflare_captcha(mock_get, mock_agent_state):
    """Regression test: Jina Reader returns HTTP 200 even when blocked by Cloudflare CAPTCHA.
    search_web_node must NOT overwrite the valid DuckDuckGo snippet with the CAPTCHA wall."""
    cloudflare_text = (
        "Title: Just a moment...\n\n"
        "Warning: This page maybe requiring CAPTCHA, please make sure you are authorized to access this page.\n"
        "## Performing security verification"
    )
    mock_get.return_value = MagicMock(status_code=200, text=cloudflare_text)
    with patch("src.tools.research_tools.web_search") as mock_ddg:
        mock_ddg.return_value = [
            {
                "url": "https://www.alphaxiv.org/es/abs/2607.18138",
                "content": "Comunicaciones de agentes de IA en redes 6G nativas de IA.",
                "title": "Comunicaciones de agentes de IA en redes 6G",
            }
        ]
        result = search_web_node(mock_agent_state)

    assert len(result["web_research"]) == 1
    assert result["web_research"][0]["content"] == "Comunicaciones de agentes de IA en redes 6G nativas de IA."
    assert "Performing security verification" not in result["web_research"][0]["content"]


def test_sanitize_arxiv_query_strips_colons_and_stopwords():
    from src.tools.research_tools import sanitize_arxiv_query
    raw = "IA agentica en redes 6G: estado del arte, evolución y estandarización en 3gpp"
    sanitized = sanitize_arxiv_query(raw)
    assert ":" not in sanitized
    assert "6G" in sanitized
    assert "3gpp" in sanitized
    assert " en " not in f" {sanitized.lower()} "
    assert " del " not in f" {sanitized.lower()} "


@patch("arxiv.Client")
@patch("arxiv.Search")
def test_search_arxiv_node_filters_out_besiii_particle_physics_and_caps_authors(
    mock_search_class, mock_client_class, mock_agent_state
):
    """Regression test: BESIII e+e- particle physics papers with 500 authors must be rejected
    on 6G/AI topics, and valid papers with >5 authors must have their author list capped with 'et al.'."""
    mock_agent_state["topic"] = "IA agentica en redes 6G: estado del arte, evolución y estandarización en 3gpp"
    mock_agent_state["queries"] = {"en": "Agentic AI in 6G networks: 3GPP standardization"}

    besiii_paper = MagicMock()
    besiii_paper.title = r"Observation of the $Y(4230)$ in $e^{+}e^{-}\to K_{S}^{0} K_{S}^{0} J/\psi$"
    besiii_paper.summary = "Cross sections at center-of-mass energies from 4.128 to 4.950 GeV collected by the BESIII detector at BEPCII."
    besiii_paper.entry_id = "http://arxiv.org/abs/2211.08561v5"
    besiii_paper.authors = [MagicMock(name=f"Physics Author {i}") for i in range(100)]

    valid_6g_paper = MagicMock()
    valid_6g_paper.title = "LLM-Driven Agentic AI for 5G and 6G Networks: Architecture and 3GPP Standardization"
    valid_6g_paper.summary = "Agentic artificial intelligence marks a shift toward autonomous control in 6G networks."
    valid_6g_paper.entry_id = "http://arxiv.org/abs/2607.16066"
    valid_6g_paper.authors = [MagicMock() for _ in range(8)]
    for idx, a in enumerate(valid_6g_paper.authors, start=1):
        a.name = f"Telecom Researcher {idx}"

    mock_client_class.return_value.results.return_value = iter([besiii_paper, valid_6g_paper])

    result = search_arxiv_node(mock_agent_state)

    assert len(result["arxiv_research"]) == 1
    item = result["arxiv_research"][0]
    assert item["url"] == "http://arxiv.org/abs/2607.16066"
    assert item["authors"].endswith("et al.")
    assert "Telecom Researcher 6" not in item["authors"]
    # Verify colon was stripped from the query sent to arxiv.Search
    sent_query = mock_search_class.call_args.kwargs["query"]
    assert ":" not in sent_query
