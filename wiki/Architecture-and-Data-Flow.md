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
│        │                                    │                   │
│        │              ┌─────────────────────┘                   │
│        │              ▼                                         │
│        │    consolidate_research (Ollama LLM, 360s timeout)     │
│        │              │                                         │
│        │              ▼                                         │
│        │    evaluate_research ──── if gaps + iter < 2 ──→ plan  │
│        │              │                                         │
│        │              ▼ (sufficient OR iter == 2)               │
│        │    generate_report → send_email → save_db → END        │
│        │                                                        │
│        └──── news_editor persona: skip evaluate loop ───────────┘
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
| `evaluate_research` | `evaluate_research_node()` | LLM evaluates sufficiency; returns JSON with gaps list |
| `generate_report` | `generate_report_node()` | Renders HTML/PDF/DOCX/MD from consolidated summary |
| `send_email` | `send_email_node()` | SMTP dispatch; skips if hash matches `last_email_hash` |
| `save_db` | `save_db_node()` | Inserts session JSON into `research_sessions.db` |
| `chat` | `chat_node()` | Conversational follow-up; detects "INVESTIGACIÓN:" trigger |

## Conditional Routing

```
evaluate_research → route_evaluation()
  │
  ├─ state["next_node"] == "plan_research"
  │   AND iteration_count < 2 → plan_research (re-plan loop)
  │
  └─ otherwise → generate_report
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
            ├─ web      → search_web_node()     (45s timeout)
            ├─ wiki     → search_wiki_node()    (10s timeout)
            ├─ arxiv    → search_arxiv_node()   (25s timeout)
            ├─ scholar  → search_scholar_node() (25s timeout)
            ├─ github   → search_github_node()  (20s timeout)
            ├─ hn       → search_hn_node()      (10s timeout)
            ├─ so       → search_so_node()      (15s timeout)
            ├─ reddit   → search_reddit_node()  (15s timeout)
            ├─ local_rag→ local_rag_node()      (no hard limit)
            └─ youtube  → _youtube_combined_node()
                            ├─ search_videos_node()   (15s)
                            └─ summarize_videos_node() (90s/video)

        All results collected via as_completed(futures_map)
        Timeout-safe: thread.join(timeout=X) + container dict
```

## AgentState (24 fields)

```python
class AgentState(TypedDict):
    # Input
    topic: str
    original_topic: str        # preserved across re-plan loops
    research_depth: str        # 'quick' | 'standard' | 'deep'
    persona: str               # 'general' | 'business' | 'tech' | 'academic' | 'pm' | 'news_editor'

    # Planning
    research_plan: List[str]   # selected source codes
    next_node: str
    iteration_count: int       # 0–2 (capped at 2)
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

    # Chat
    messages: List[BaseMessage]

    # Control
    evaluation_report: str
    last_email_hash: str       # MD5 for email idempotence
    source_metadata: Dict[str, dict]  # {'source': {'reliability': 1-5}}
```

## Self-Correction Loop

```
iteration 0:
  parallel_search → consolidate → evaluate
    → gaps found: iteration_count = 1 → plan_research (re-select sources)
    → parallel_search → consolidate → evaluate
    → still gaps: iteration_count = 2 → STOP (generate_report anyway)

iteration 0:
  parallel_search → consolidate → evaluate
    → sufficient: True → generate_report (no loop)
```

The re-plan step calls `plan_research_node()` again. The LLM receives the previous evaluation report (list of gaps and shallow topics) as context, and can select different or additional sources.

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
docker-compose up:
  - research-agent   (Streamlit :8501, src/app.py)
  - ChromaDB         (vector store, persistent /app/data/chroma_db)
  - Ollama           (LLM server :11434, model qwen3:14b)
```

Ollama must have the model pulled before first run:
```bash
docker compose exec ollama ollama pull qwen3:14b
```
