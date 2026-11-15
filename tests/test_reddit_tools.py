from unittest.mock import patch

from src.tools.reddit_tools import search_reddit_node

HIT = {"url": "http://reddit.com/r/x", "content": "DDG Reddit content", "title": "t"}


def test_search_reddit_node_restricts_the_search_to_reddit(mock_agent_state):
    with patch("src.tools.reddit_tools.duckduckgo_search", return_value=[dict(HIT)]) as mock_ddg:
        result = search_reddit_node(mock_agent_state)

    assert result["reddit_research"] == [HIT]
    assert "next_node" in result
    assert mock_ddg.call_args.args[0].endswith("site:reddit.com")
    assert mock_ddg.call_args.kwargs["timelimit"] == "y"


def test_search_reddit_node_news_editor_searches_the_last_day(mock_agent_state):
    state = {**mock_agent_state, "persona": "news_editor"}
    with patch("src.tools.reddit_tools.duckduckgo_search", return_value=[dict(HIT)]) as mock_ddg:
        search_reddit_node(state)

    assert mock_ddg.call_args.kwargs["timelimit"] == "d"


def test_search_reddit_node_returns_nothing_when_search_fails(mock_agent_state):
    with patch("src.tools.reddit_tools.duckduckgo_search", side_effect=RuntimeError("blocked")):
        result = search_reddit_node(mock_agent_state)

    assert result["reddit_research"] == []
    assert "next_node" in result
