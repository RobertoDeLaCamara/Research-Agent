"""Thin wrappers over the search/content libraries the research nodes use.

These replace the `langchain-community` loaders and tools (the package is being
sunset) with direct calls to the underlying libraries, which were already
dependencies. Each function returns plain dicts or strings; timeouts and error
handling stay in the calling node.
"""

from urllib.parse import parse_qs, urlparse

import wikipedia
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from tavily import TavilyClient
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

WIKIPEDIA_MAX_QUERY_CHARS = 300
WIKIPEDIA_MAX_CONTENT_CHARS = 4000
_YOUTUBE_HOSTS = {"youtu.be", "m.youtube.com", "youtube.com", "www.youtube.com",
                  "www.youtube-nocookie.com", "vid.plus"}


def tavily_search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Search the web with Tavily. Returns dicts with `url`, `content`, `title`."""
    response = TavilyClient(api_key=api_key).search(query=query, max_results=max_results)
    return [
        {"url": r.get("url"), "content": r.get("content"), "title": r.get("title")}
        for r in response.get("results", [])
    ]


def duckduckgo_search(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo (worldwide, past year). Returns one dict per hit with `url`, `content`, `title`."""
    try:
        hits = DDGS().text(
            query, region="wt-wt", safesearch="moderate", timelimit="y", max_results=max_results
        ) or []
    except DDGSException as e:
        # ddgs raises instead of returning an empty list; anything else is a real failure
        if "No results found" not in str(e):
            raise
        hits = []
    return [
        {"url": h.get("href"), "content": h.get("body"), "title": h.get("title")}
        for h in hits
        if h.get("body")
    ]


def wikipedia_pages(query: str, lang: str = "en", max_docs: int = 1) -> list[dict]:
    """Return up to `max_docs` Wikipedia pages as dicts with `title`, `content`, `url`.

    Titles that do not resolve to a single page (missing or disambiguation) are skipped.
    """
    wikipedia.set_lang(lang)
    pages = []
    for title in wikipedia.search(query[:WIKIPEDIA_MAX_QUERY_CHARS], results=max_docs):
        try:
            page = wikipedia.page(title=title, auto_suggest=False)
        except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError):
            continue
        pages.append({
            "title": title,
            "content": page.content[:WIKIPEDIA_MAX_CONTENT_CHARS],
            "url": page.url,
        })
    return pages


def youtube_video_id(url: str) -> str:
    """Extract the 11-character video id from a YouTube URL."""
    parsed = urlparse(url)
    video_id = None
    if parsed.scheme in {"http", "https"} and parsed.netloc in _YOUTUBE_HOSTS:
        if parsed.path.endswith("/watch"):
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            video_id = parsed.path.lstrip("/").split("/")[-1]
    if not video_id or len(video_id) != 11:
        raise ValueError(f'Could not determine the video ID for the URL "{url}".')
    return video_id


def youtube_transcript(url: str, languages: tuple[str, ...] = ("es", "en")) -> str:
    """Return the transcript of a YouTube video as one string ("" if disabled).

    Tries `languages` in order, then English.
    """
    try:
        transcripts = YouTubeTranscriptApi().list(youtube_video_id(url))
    except TranscriptsDisabled:
        return ""
    try:
        transcript = transcripts.find_transcript(list(languages))
    except NoTranscriptFound:
        transcript = transcripts.find_transcript(["en"])
    return " ".join(snippet.text.strip(" ") for snippet in transcript.fetch().snippets)
