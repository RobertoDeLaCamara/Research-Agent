from unittest.mock import MagicMock, patch

import pytest

from src.tools import source_loaders
from src.tools.source_loaders import (
    duckduckgo_search,
    tavily_search,
    wikipedia_pages,
    youtube_transcript,
    youtube_video_id,
)


def test_tavily_search_passes_key_and_limit():
    with patch("src.tools.source_loaders.TavilyClient") as mock_client:
        mock_client.return_value.search.return_value = {
            "results": [{"url": "http://a.com", "content": "A", "title": "TA", "score": 0.9}]
        }

        results = tavily_search("llm agents", api_key="k", max_results=3)

    mock_client.assert_called_once_with(api_key="k")
    mock_client.return_value.search.assert_called_once_with(query="llm agents", max_results=3)
    assert results == [{"url": "http://a.com", "content": "A", "title": "TA"}]


def test_tavily_search_without_results_key():
    with patch("src.tools.source_loaders.TavilyClient") as mock_client:
        mock_client.return_value.search.return_value = {}
        assert tavily_search("q", api_key="k") == []


def test_duckduckgo_search_maps_fields_and_drops_empty_hits():
    with patch("src.tools.source_loaders.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.return_value = [
            {"title": "T1", "href": "http://one.com", "body": "Body 1"},
            {"title": "T2", "href": "http://two.com", "body": ""},
        ]

        results = duckduckgo_search("query", max_results=4)

    mock_ddgs.return_value.text.assert_called_once_with(
        "query", region="wt-wt", safesearch="moderate", timelimit="y", max_results=4
    )
    assert results == [{"url": "http://one.com", "content": "Body 1", "title": "T1"}]


def test_duckduckgo_search_no_hits():
    with patch("src.tools.source_loaders.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.return_value = None
        assert duckduckgo_search("query") == []


def test_wikipedia_pages_skips_unresolvable_titles():
    real_exceptions = source_loaders.wikipedia.exceptions
    good_page = MagicMock(content="x" * 5000, url="http://wiki/Good")

    def fake_page(title, auto_suggest):
        assert auto_suggest is False
        if title == "Missing":
            raise real_exceptions.PageError(title)
        if title == "Ambiguous":
            raise real_exceptions.DisambiguationError(title, ["a", "b"])
        return good_page

    with patch("src.tools.source_loaders.wikipedia") as mock_wiki:
        mock_wiki.exceptions = real_exceptions
        mock_wiki.search.return_value = ["Missing", "Ambiguous", "Good"]
        mock_wiki.page.side_effect = fake_page

        pages = wikipedia_pages("q" * 400, lang="es", max_docs=3)

    mock_wiki.set_lang.assert_called_once_with("es")
    mock_wiki.search.assert_called_once_with("q" * 300, results=3)
    assert pages == [{"title": "Good", "content": "x" * 4000, "url": "http://wiki/Good"}]


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
])
def test_youtube_video_id(url):
    assert youtube_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    "https://youtube.com/watch?v=short",
    "https://youtube.com/watch?list=abc",
    "https://example.com/watch?v=dQw4w9WgXcQ",
    "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    "not a url",
])
def test_youtube_video_id_rejects_invalid(url):
    with pytest.raises(ValueError):
        youtube_video_id(url)


def _transcript(*texts):
    transcript = MagicMock()
    transcript.fetch.return_value.snippets = [MagicMock(text=t) for t in texts]
    return transcript


def test_youtube_transcript_joins_snippets():
    with patch("src.tools.source_loaders.YouTubeTranscriptApi") as mock_api:
        transcripts = mock_api.return_value.list.return_value
        transcripts.find_transcript.return_value = _transcript(" hola ", "mundo")

        text = youtube_transcript("https://youtu.be/dQw4w9WgXcQ", languages=("es", "en"))

    mock_api.return_value.list.assert_called_once_with("dQw4w9WgXcQ")
    transcripts.find_transcript.assert_called_once_with(["es", "en"])
    assert text == "hola mundo"


def test_youtube_transcript_falls_back_to_english():
    with patch("src.tools.source_loaders.YouTubeTranscriptApi") as mock_api:
        transcripts = mock_api.return_value.list.return_value
        transcripts.find_transcript.side_effect = [
            source_loaders.NoTranscriptFound("dQw4w9WgXcQ", ["fr"], MagicMock()),
            _transcript("hello"),
        ]

        text = youtube_transcript("https://youtu.be/dQw4w9WgXcQ", languages=("fr",))

    assert transcripts.find_transcript.call_args_list[1].args == (["en"],)
    assert text == "hello"


def test_youtube_transcript_disabled_returns_empty():
    with patch("src.tools.source_loaders.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.list.side_effect = source_loaders.TranscriptsDisabled("dQw4w9WgXcQ")
        assert youtube_transcript("https://youtu.be/dQw4w9WgXcQ") == ""


def test_duckduckgo_search_no_results_exception_is_empty():
    with patch("src.tools.source_loaders.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.side_effect = source_loaders.DDGSException("No results found.")
        assert duckduckgo_search("query") == []


def test_duckduckgo_search_other_errors_propagate():
    with patch("src.tools.source_loaders.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.side_effect = source_loaders.DDGSException("ratelimit")
        with pytest.raises(source_loaders.DDGSException):
            duckduckgo_search("query")
