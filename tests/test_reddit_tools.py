from unittest.mock import patch

from src.tools.reddit_tools import search_reddit_node

HIT = {"url": "http://reddit.com/r/x", "content": "DDG Reddit content", "title": "t"}


def test_search_reddit_node_restricts_the_search_to_reddit(mock_agent_state):
    with patch("src.tools.reddit_tools.web_search", return_value=[dict(HIT)]) as mock_ddg:
        result = search_reddit_node(mock_agent_state)

    assert result["reddit_research"] == [HIT]
    assert "next_node" in result
    assert mock_ddg.call_args.args[0].endswith("site:reddit.com")
    assert mock_ddg.call_args.kwargs["timelimit"] == "y"


def test_search_reddit_node_news_editor_searches_the_last_day(mock_agent_state):
    state = {**mock_agent_state, "persona": "news_editor"}
    with patch("src.tools.reddit_tools.web_search", return_value=[dict(HIT)]) as mock_ddg:
        search_reddit_node(state)

    assert mock_ddg.call_args.kwargs["timelimit"] == "d"


def test_search_reddit_node_returns_nothing_when_search_fails(mock_agent_state):
    with patch("src.tools.reddit_tools.web_search", side_effect=RuntimeError("blocked")):
        result = search_reddit_node(mock_agent_state)

    assert result["reddit_research"] == []
    assert "next_node" in result


def test_search_reddit_node_filters_video_stubs_and_wifi_6ghz_on_6g_topic(mock_agent_state):
    """Regression test: filter out reddit.com/video stubs and WiFi 6GHz posts when searching 6G mobile."""
    state = {
        **mock_agent_state,
        "topic": "IA agentica en redes 6G",
        "queries": {"en": "Agentic AI in 6G cellular networks"},
    }
    raw_hits = [
        {
            "url": "https://www.reddit.com/video/spr34iqnkp521",
            "content": "We would like to show you a description here but the site won’t allow us.",
            "title": "Reddit Video",
        },
        {
            "url": "https://www.reddit.com/r/HomeNetworking/comments/18io0r4/wifi_6ghz_not_as_fast/",
            "content": "Do y'all think it's still worth using the 6ghz band under these conditions? I know Wifi 6 is supposed to have other benefits.",
            "title": "WiFi 6GHz",
        },
        {
            "url": "https://www.reddit.com/r/telecom/comments/abc123/3gpp_release_20_6g_ai_agents/",
            "content": "Discussion on 3GPP Release 20 6G autonomous AI agents in RAN and Core.",
            "title": "3GPP 6G AI Agents",
        },
    ]
    with patch("src.tools.reddit_tools.web_search", return_value=raw_hits):
        result = search_reddit_node(state)

    assert [r["url"] for r in result["reddit_research"]] == [
        "https://www.reddit.com/r/telecom/comments/abc123/3gpp_release_20_6g_ai_agents/"
    ]


def test_is_reddit_result_relevant_filters_bing_aclick_and_offtopic_gaming():
    from src.tools.reddit_tools import is_reddit_result_relevant
    query = "Agentic AI in 6G networks: state of the art, evolution, and standardization in 3GPP"
    bing_ad = {
        "title": "Leading AI-RAN Alliance & 6G - Networks for AI",
        "url": "https://www.bing.com/aclick?ld=e8ArpwonPKdB",
        "content": "Sponsored link for 6G networks.",
    }
    gaming_post = {
        "title": "Cool Aigis art that was accused of being made by AI",
        "url": "https://www.reddit.com/r/PERSoNA/comments/1ce9tua/cool_aigis_art/",
        "content": "Persona 3 Reload fan art discussion.",
    }
    assert is_reddit_result_relevant(bing_ad, query) is False
    assert is_reddit_result_relevant(gaming_post, query) is False
