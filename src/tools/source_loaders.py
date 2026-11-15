"""Thin wrappers over the search/content libraries the research nodes use.

These replace the `langchain-community` loaders and tools (the package is being
sunset) with direct calls to the underlying libraries, which were already
dependencies. Each function returns plain dicts or strings; timeouts and error
handling stay in the calling node.
"""

import time
from urllib.parse import parse_qs, urlparse

import wikipedia
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

# "wt-wt" (worldwide) makes the ddgs Wikipedia engine query wt.wikipedia.org, which does not exist
DDG_REGION = "us-en"
DDG_ATTEMPTS = 3
DDG_RETRY_DELAY = 1.0
WIKIPEDIA_MAX_QUERY_CHARS = 300
WIKIPEDIA_MAX_CONTENT_CHARS = 4000
_YOUTUBE_HOSTS = {"youtu.be", "m.youtube.com", "youtube.com", "www.youtube.com",
                  "www.youtube-nocookie.com", "vid.plus"}

_BOT_BLOCK_PATTERNS = (
    "just a moment...",
    "title: just a moment",
    "performing security verification",
    "this page maybe requiring captcha",
    "requiring captcha",
    "verifies you are not a bot",
    "verify you are human",
    "enable javascript and cookies to continue",
    "attention required! | cloudflare",
    "we would like to show you a description here but the site won't allow us",
    "we would like to show you a description here but the site won’t allow us",
    "please enable js and disable any ad blocker",
)


def is_bot_block_or_stub(text: str, title: str = "") -> bool:
    """Return True when scraped content or snippet is an anti-bot/CAPTCHA interstitial or robots.txt stub."""
    if not (text or "").strip():
        return True
    combined = f"{title or ''}\n{text or ''}".strip().lower()
    return any(pat in combined for pat in _BOT_BLOCK_PATTERNS)


def _ddgs_text(query: str, max_results: int, timelimit: str | None) -> list[dict]:
    """One ddgs attempt. Returns [] when the engines answered with no results."""
    try:
        return DDGS().text(
            query, region=DDG_REGION, safesearch="moderate", timelimit=timelimit, max_results=max_results
        ) or []
    except DDGSException as e:
        # ddgs raises instead of returning an empty list; anything else is a real failure
        if "No results found" not in str(e):
            raise
        return []


def duckduckgo_search(query: str, max_results: int = 5, timelimit: str | None = "y") -> list[dict]:
    """Search the web through ddgs (DuckDuckGo and the other engines it aggregates). No API key.

    `timelimit` is "d", "w", "m", "y" or None. The engines behind ddgs are scraped and
    often return nothing or fail on a single request, so this tries up to
    `DDG_ATTEMPTS` times; the retries drop a "y" time limit, which is the usual
    reason for an empty answer. Narrower limits ("d", "w", "m") are kept, since
    they are the point of the query. Returns one dict per hit with `url`, `content`, `title`.
    """
    hits: list[dict] = []
    last_error: DDGSException | None = None
    for attempt in range(DDG_ATTEMPTS):
        last = attempt == DDG_ATTEMPTS - 1
        limit = None if (attempt > 0 and timelimit == "y") else timelimit
        try:
            hits = _ddgs_text(query, max_results, limit)
            last_error = None
        except DDGSException as e:
            last_error = e
            hits = []
        if hits:
            break
        if not last:
            time.sleep(DDG_RETRY_DELAY)
    if not hits and last_error is not None:
        raise last_error
    return [
        {"url": h.get("href"), "content": h.get("body"), "title": h.get("title")}
        for h in hits
        if h.get("body") and not is_bot_block_or_stub(h.get("body", ""), h.get("title", ""))
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
