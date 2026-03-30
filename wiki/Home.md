# Research-Agent — Wiki

LangGraph-based research orchestration system. Fans out queries across 10 sources in parallel (ThreadPoolExecutor), synthesizes results with an Ollama LLM, and self-corrects up to 2 times if quality evaluation finds gaps. Outputs HTML/PDF/DOCX/Markdown reports. Streamlit UI + CLI mode.

## Quick Start

```bash
# Docker (recommended)
docker compose up -d
# Access Streamlit at http://localhost:8501

# Local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# CLI
docker compose run --rm research-agent python src/main.py "Your Topic"

# Streamlit UI (local)
streamlit run src/app.py --server.address=0.0.0.0
```

## Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | LangGraph (StateGraph) |
| LLM | Ollama — `qwen3:14b` (default) |
| Search | Tavily (primary), DuckDuckGo (fallback) |
| Vector store | ChromaDB (`all-MiniLM-L6-v2` embeddings) |
| RAG cache | SQLite (`rag_cache.db`) |
| Session storage | SQLite (`research_sessions.db`) |
| UI | Streamlit |
| Parallelism | `ThreadPoolExecutor` (one thread per source) |
| Reports | FPDF (PDF), python-docx (DOCX), Markdown, HTML |

## Research Sources

| Source | Code | Timeout | Library |
|--------|------|---------|---------|
| Web search | `web` | 45s | Tavily → DuckDuckGo fallback |
| Wikipedia | `wiki` | 10s | `WikipediaLoader` |
| arXiv | `arxiv` | 25s | `arxiv.Client` |
| Semantic Scholar | `scholar` | 25s | `semanticscholar` |
| GitHub | `github` | 20s | `PyGithub` |
| Hacker News | `hn` | 10s | Algolia HN API |
| Stack Overflow | `so` | 15s | `stackapi.StackAPI` |
| Reddit | `reddit` | 15s | Tavily (site:reddit.com) |
| YouTube | `youtube` | 15s + 90s/video | `youtube-search` + transcript |
| Local RAG | `local_rag` | — | ChromaDB + SQLite keyword |

## Personas

| Display Name | Code | Style |
|---|---|---|
| Generalista | `general` | Professional, balanced |
| Analista de Mercado | `business` | ROI-focused, strategic impact |
| Arquitecto de Software | `tech` | Technical, implementation-focused |
| Revisor Científico | `academic` | Peer-review rigor, methodology |
| Product Manager | `pm` | User needs, feature prioritization |
| Editor de Noticias | `news_editor` | Immediacy, Daily Digest + TL;DR format |

## Research Depths

| Mode | Code | Word Count | Characteristics |
|------|------|------------|-----------------|
| Rápido | `quick` | 800–1500 | Main points only |
| Estándar | `standard` | 2000–3500 | 3–5 key points, multi-source evidence |
| Profundo | `deep` | 3500–6000 | Cross-source comparison, critical analysis |

## Wiki Pages

- [Architecture and Data Flow](Architecture-and-Data-Flow.md)
- [Research Sources](Research-Sources.md)
- [RAG Pipeline](RAG-Pipeline.md)
- [Personas and Depth Modes](Personas-and-Depth-Modes.md)
- [Database and Sessions](Database-and-Sessions.md)
- [Development Guide](Development-Guide.md)

## Key Layout

```
src/
├── agent.py                 LangGraph graph definition (9 nodes, conditional edges)
├── state.py                 AgentState TypedDict (24 fields)
├── config.py                Pydantic Settings (Ollama URL, API keys, timeouts)
├── db_manager.py            SQLite: research_sessions + cleanup
├── app.py                   Streamlit UI
├── main.py                  CLI entry point
└── tools/
    ├── parallel_tools.py    ThreadPoolExecutor fan-out across all sources
    ├── research_tools.py    10 source-specific fetch functions
    ├── rag_tools.py         ChromaDB + SQLite hybrid retrieval
    ├── synthesis_tools.py   Ollama LLM synthesis, persona prompts
    ├── reporting_tools.py   HTML/PDF/DOCX/MD report generation
    ├── router_tools.py      LLM planning, evaluation, re-plan logic
    ├── chat_tools.py        Conversational follow-up node
    └── translation_tools.py Multilingual query expansion

tests/
knowledge_base/             Local files for RAG (PDF, TXT)
reports/                    Generated output files
```

## Non-Obvious Facts

- **YouTube runs sequentially within its thread** — transcript summarization depends on search results, so `search_videos_node` and `summarize_videos_node` run in series inside one thread.
- **`news_editor` skips quality evaluation** — the re-plan loop is bypassed entirely for this persona; immediacy takes priority over depth.
- **Self-correction is capped at 2 iterations** — `iteration_count` is checked before re-planning; hitting the cap goes directly to report generation regardless of evaluation result.
- **Email is idempotent** — an MD5 hash of the report content is stored in state; if `last_email_hash` matches, the send is skipped.
- **Thread-safe results use container dicts** — each source function writes to `container = {"data": []}` inside its thread rather than returning a value; the main thread reads after `join(timeout=X)`.
- **LLM synthesis timeout is 6 minutes** — `synthesis_request_timeout = 360s`; this is the single longest operation.
- **Local RAG is opt-in** — not checked by default in the Streamlit sidebar; user must enable "Include local knowledge base".
- **Source reliability scores embedded in context** — 1–5 scores per source type are passed to the LLM during synthesis (local_rag/wiki/arxiv = 5, reddit = 2).
