# Architecture and Data Flow

## System Overview

```
User Input (topic, persona, depth, sources)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph StateGraph — src/agent.py                            │
│                                                                 │
│  initialize_state → plan_research → parallel_search             │
│                                           │                     │
│                                           ▼                     │
│                       consolidate_research (Ollama LLM, 360s)   │
│                                           │                     │
│                                           ▼                     │
│                       evaluate_research (fact-check; dubious    │
│                         claims appended as a report warning)    │
│                                           │                     │
│                                           ▼                     │
│  generate_report → send_email → save_db → END                   │
│  (store_session_memory() is called inside generate_report)      │
│                                                                 │
│  news_editor / quick: evaluate_research returns immediately     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## LangGraph Node Reference

| Node | Function | Description |
|------|----------|-------------|
| `initialize_state` | `initialize_state_node()` | Defaults all AgentState fields |
| `plan_research` | `plan_research_node()` | LLM selects sources from plan; expands queries multilingual |
| `parallel_search` | `parallel_search_node()` | ThreadPoolExecutor fan-out; one thread per source |
| `consolidate_research` | `consolidate_research_node()` | Ollama LLM synthesis with persona + depth prompt |
| `evaluate_research` | `evaluate_research_node()` | LLM fact-check; returns JSON with `dubious_claims` and `reasoning`. Dubious claims are appended to the summary as a warning. Skipped for quick depth and news_editor persona. |
| `generate_report` | `generate_report_node()` | Renders HTML/PDF/DOCX/MD from consolidated summary. Includes word count and reading time. Triggers `store_session_memory()` for cross-session ChromaDB persistence. |
| `send_email` | `send_email_node()` | SMTP dispatch; skips if hash matches `last_email_hash` |
| `save_db` | `save_db_node()` | Inserts session JSON into `research_sessions.db` |
| `chat` | `chat_node()` | Conversational follow-up; detects "INVESTIGACIÓN:" trigger |

## Conditional Routing

```
evaluate_research → route_evaluation()
  │
  ├─ state["next_node"] == "plan_research" → plan_research
  │   (defined in the graph, but evaluate_research_node currently
  │    always returns "END", so this branch is never taken)
  │
  └─ "END" → generate_report
```

```
chat → route_chat()
  │
  ├─ AI response contains "INVESTIGACIÓN:" → plan_research
  ├─ User message contains research keyword → plan_research
  └─ default → send_email
```

## Parallel Search Flow

```
parallel_search_node()
        │
        ├─ max_workers = len(selected_sources)
        │
        └─ ThreadPoolExecutor:
            │
            ├─ web      → search_web_node()     (12s timeout)
            ├─ wiki     → search_wiki_node()    (10s timeout)
            ├─ arxiv    → search_arxiv_node()   (12s timeout)
            ├─ scholar  → search_scholar_node() (25s timeout)
            ├─ github   → search_github_node()  (20s timeout)
            ├─ hn       → search_hn_node()      (10s timeout)
            ├─ so       → search_so_node()      (15s timeout)
            ├─ reddit   → search_reddit_node()  (15s timeout)
            ├─ local_rag→ local_rag_node()      (no hard limit)
            └─ youtube  → _youtube_combined_node()
                            ├─ search_videos_node()   (15s)
                            └─ summarize_videos_node() (25s/video)

        All results collected via as_completed(futures_map, timeout=60)
        Timeout-safe: thread.join(timeout=X) + container dict
```

## AgentState (32 fields)

```python
class AgentState(TypedDict):
    # Input
    topic: str
    original_topic: str        # preserved original request
    research_depth: str        # 'quick' | 'standard' | 'deep'
    persona: str               # 'general' | 'business' | 'tech' | 'academic' | 'pm' | 'news_editor'

    # Planning
    research_plan: List[str]   # selected source codes
    next_node: str
    iteration_count: int       # initialised to 0; not incremented by any current node
    queries: Dict[str, str]    # {'en': '...', 'es': '...'}

    # Research Results (per-source lists of dicts)
    web_research: List[dict]
    wiki_research: List[dict]
    arxiv_research: List[dict]
    github_research: List[dict]
    scholar_research: List[dict]
    hn_research: List[dict]
    so_research: List[dict]
    reddit_research: List[dict]
    local_research: List[dict]
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]       # YouTube transcripts

    # Output
    consolidated_summary: str
    report: str                # HTML report
    bibliography: List[str]
    pdf_path: str
    docx_path: str             # set by generate_report_node
    md_path: str               # set by generate_report_node
    report_language: str       # 'es' | 'en'
    use_rag: bool              # include local RAG as a source

    # Chat
    messages: List[BaseMessage]

    # Control
    evaluation_report: str
    last_email_hash: str       # MD5 for email idempotence
    source_metadata: Dict[str, dict]  # {'source': {'reliability': 1-5}}
```

## Fact-Check Step

```
parallel_search → consolidate → evaluate
  → dubious_claims found: warning appended to consolidated_summary → generate_report
  → none / evaluation error:                                          → generate_report
```

There is no automatic re-plan loop: `evaluate_research_node` always returns `next_node = "END"`. The `evaluate_research → plan_research` conditional edge is still wired in `src/agent.py` but never taken.

## Report Generation

```
consolidated_summary
        │
        ├─ HTML   → reports/reporte_final.html
        │           (CSS variables, responsive, source badges)
        │
        ├─ Markdown → reports/reporte_{topic}.md
        │
        ├─ DOCX   → reports/reporte_final.docx
        │           (python-docx Document)
        │
        └─ PDF    → reports/reporte_investigacion.pdf
                    (FPDF, Helvetica, ASCII-safe text)
```

## Container Startup (Docker)

```
Compose services (docker-compose.full.yml):
  - research-agent   (Streamlit, src/app.py; ChromaDB embedded,
                      persisted in /app/data/chroma_db)
  - ollama + ollama-init (LLM server :11434, model pre-pull)
```

In `docker-compose.full.yml` the `ollama-init` service pulls `qwen2.5:1.5b` automatically. To use another model:
```bash
docker compose -f docker-compose.full.yml exec ollama ollama pull qwen3:14b
```
and set `OLLAMA_MODEL` accordingly.
