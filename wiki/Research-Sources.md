# Research Sources

## Source Selection

At the `plan_research` node, the LLM receives a list of available sources with descriptions and selects which ones to query based on the topic. Selection happens once per run: the evaluation step never sends the graph back to planning.

All sources are opt-in via the Streamlit sidebar. Local RAG is off by default.

## Source Details

### Web Search (`web`)

```
Search: DuckDuckGo (ddgs library, no API key, one result per hit)
  - Results from the past year; up to 3 attempts, the retries without the time limit

Post-processing:
  - Jina Reader enhancement: GET r.jina.ai/{url}
    → ThreadPoolExecutor (5 workers), 3s timeout per URL
  - Hits and fetched pages that are bot-block / CAPTCHA interstitials ("Just a moment...", Cloudflare
    checks, robots.txt stubs) or ad redirects (bing.com/aclick) are discarded; the search snippet is kept
    when only the page fetch was blocked.
  - Synthesis context limit: config.max_synthesis_context_chars = 25000 (for all sources together)

Timeout: config.web_search_timeout (12 seconds, thread.join)
Max results: config.max_results_per_source (default: 5)
```

### Wikipedia (`wiki`)

```
Library: wikipedia (via src/tools/source_loaders.py)
Language: auto-detected (Spanish / English)
Max docs: 1 (quick/standard) | 3 (deep)
Content preview: 1000 chars + "..."
Timeout: 10 seconds
```

### arXiv (`arxiv`)

```
Library: arxiv.Client (direct SDK)
Sort: arxiv.SortCriterion.Relevance
Fields extracted: title, summary, authors (capped at 5, then "et al."), entry_id (URL)
Query: the topic is sanitised first (colons and punctuation become spaces)
Relevance filter: a hit must contain at least one query keyword; high-energy collision papers
  are dropped unless the query is about physics
Max results: set by research depth
Timeout: 12 seconds
```

Reliability score: 5/5 (scientific, peer-reviewed).

### Semantic Scholar (`scholar`)

```
Library: semanticscholar.SemanticScholar
Method: sch.search_paper(query, limit=max_results,
                         fields=['title','abstract','url','year','authors'])
Timeout: 25 seconds
Note: Iterator must be consumed inside thread to respect timeout
```

Reliability score: 5/5 (academic, curated).

### GitHub (`github`)

```
Library: PyGithub
Primary query: "{topic} language:python" (sorted by stars)
Fallback: global topic search if primary returns 0 results (checks totalCount)
README fetch: conditional on persona (tech / pm / arquitecto / architect)
  → ThreadPoolExecutor (5 workers) for parallel README fetching
Timeout: 20 seconds
```

Reliability score: 4/5.

### Hacker News (`hn`)

```
API: Algolia HN API
URL: https://hn.algolia.com/api/v1/search?query={query}&tags=story
Fields: title, objectID (→ URL: news.ycombinator.com/item?id={objectID}),
        author, points, num_comments
Timeout: 10 seconds
```

Reliability score: 4/5.

### Stack Overflow (`so`)

```
Library: stackapi.StackAPI
Method: SITE.fetch('search/advanced', q=query, sort='relevance',
                   order='desc', filter='withbody')
Body inclusion: conditional on persona
  → tech / pm / arquitecto / architect: full body
  → others: title only
Timeout: 15 seconds
```

Reliability score: 4/5.

### Reddit (`reddit`)

```
Search: DuckDuckGo (ddgs library, no API key) with site:reddit.com
Time range: "d" (last 24 hours) for news_editor persona
Relevance filter: drops non-Reddit links, blocked stubs and media-only links (v.redd.it, reddit.com/video);
  for 6G / 3GPP / agentic queries the post must contain one of those terms, and WiFi 6 / 6 GHz posts
  are dropped on cellular 6G queries
Timeout: 15 seconds
```

Reliability score: 2/5 (community opinion, informal).

### YouTube (`youtube`)

```
Search: youtube_search.YoutubeSearch
  → Extracts: video ID, title, channel, URL
  → Timeout: 15 seconds

Summarization (sequential within same thread):
  → Transcript: youtube-transcript-api, languages ['es', 'en'] then 'en'
  → Timeout: 10 seconds for transcript load
  → Summary chain: load_summarize_chain (map_reduce)
  → Timeout: 25 seconds per video summary
  → Fallback: LLM-generated summary from title if transcript unavailable
```

YouTube runs sequentially within its thread: search must complete before summarization starts.

### Local RAG (`local_rag`)

See [RAG Pipeline](RAG-Pipeline.md) for full details.

```
Directory: RAG_KB_DIR env var (default: ./knowledge_base)
Formats: .pdf, .txt
Hybrid retrieval: ChromaDB semantic + SQLite keyword (RAG_MODE=hybrid)
Checkbox in the Streamlit UI: off by default, on when BOOKS_RAG_URL is set (USE_RAG_DEFAULT overrides)
```

Reliability score: 5/5 (user-provided, highest authority).

## Source Reliability Matrix

| Source | Score | Reason |
|--------|-------|--------|
| `local_rag` | 5 | User-curated, most trusted |
| `wiki` | 5 | Official, maintained |
| `arxiv` | 5 | Peer-reviewed science |
| `scholar` | 5 | Academic, curated |
| `github` | 4 | Code-backed, community |
| `hn` | 4 | Tech community, reputation |
| `so` | 4 | Q&A with rep system |
| `web` | 3 | Variable quality |
| `reddit` | 2 | Informal opinion |

Scores are passed to the LLM in the synthesis context so it can weight sources appropriately.

## Multilingual Query Expansion

Before fan-out, `expand_queries_multilingual()` translates the topic to English and Spanish (minimum). Additional languages (zh, de, fr, ja) are available via config. The expanded queries dict is stored in `state["queries"]` and individual source functions choose the most appropriate language.

```python
# Example output for "inteligencia artificial en educación"
queries = {
    "es": "inteligencia artificial en educación",
    "en": "artificial intelligence in education"
}
```
