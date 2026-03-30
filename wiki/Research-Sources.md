# Research Sources

## Source Selection

At the `plan_research` node, the LLM receives a list of available sources with descriptions and selects which ones to query based on the topic. Selection can differ between the initial plan and any re-plan iteration (re-plans receive the evaluation report with identified gaps as context).

All sources are opt-in via the Streamlit sidebar. Local RAG is off by default.

## Source Details

### Web Search (`web`)

```
Primary: TavilySearchResults (requires TAVILY_API_KEY)
Fallback: DuckDuckGoSearchRun

Post-processing:
  - Jina Reader enhancement: GET r.jina.ai/{url}
    → ThreadPoolExecutor (5 workers), 3s timeout per URL
  - Content length limit: config.max_synthesis_context_chars = 50000

Timeout: 45 seconds (thread.join)
Max results: config.max_results_per_source (default: 5)
```

### Wikipedia (`wiki`)

```
Library: langchain_community.document_loaders.WikipediaLoader
Language: auto-detected (Spanish / English)
Max docs: 1 (quick/standard) | 3 (deep)
Content preview: 1000 chars + "..."
Timeout: 10 seconds
```

### arXiv (`arxiv`)

```
Library: arxiv.Client (direct SDK)
Sort: arxiv.SortCriterion.Relevance
Fields extracted: title, summary, authors, entry_id (URL)
Max results: config.max_results_per_source
Timeout: 25 seconds
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
Primary: TavilyClient with site:reddit.com
Fallback: DuckDuckGoSearchRun
Time range: "d" (last 24 hours) for news_editor persona
Search depth: "advanced"
Timeout: 15 seconds
```

Reliability score: 2/5 (community opinion, informal).

### YouTube (`youtube`)

```
Search: youtube_search.YoutubeSearch
  → Extracts: video ID, title, channel, URL
  → Timeout: 15 seconds

Summarization (sequential within same thread):
  → Transcript: YoutubeLoader.from_youtube_url(languages=['es', 'en'])
  → Timeout: 20 seconds for transcript load
  → Summary chain: load_summarize_chain (map_reduce)
  → Timeout: 90 seconds per video
  → Fallback: LLM-generated summary from title if transcript unavailable
```

YouTube runs sequentially within its thread: search must complete before summarization starts.

### Local RAG (`local_rag`)

See [RAG Pipeline](RAG-Pipeline.md) for full details.

```
Directory: RAG_KB_DIR env var (default: ./knowledge_base)
Formats: .pdf, .txt
Hybrid retrieval: ChromaDB semantic + SQLite keyword
Off by default in Streamlit UI
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
