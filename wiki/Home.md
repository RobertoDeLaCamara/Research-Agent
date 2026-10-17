# Research-Agent — Wiki

LangGraph-based research orchestration system. Fans out queries across 10 sources in parallel (ThreadPoolExecutor), synthesizes results with an Ollama LLM, and fact-checks the synthesis (skipped for Quick depth) and appends a warning to the report if factually dubious claims are detected; no re-plan loop is triggered. Each session is persisted to a ChromaDB memory collection; the planner retrieves past findings on subsequent queries to avoid re-investigating the same ground. Outputs HTML/PDF/DOCX/Markdown reports. Streamlit UI + CLI mode.

## Quick Start

```bash
# Docker (recommended)
docker compose up -d   # minimal compose: 8501 -> 7860, bring your own Ollama
# Access Streamlit at http://localhost:8501

# Local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env

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
| RAG cache | JSON file (`rag_cache.json`) |
| Session storage | SQLite (`research_sessions.db`) |
| UI | Streamlit |
| Parallelism | `ThreadPoolExecutor` (one thread per source) |
| Reports | FPDF (PDF), python-docx (DOCX), Markdown, HTML |

## Research Sources

| Source | Code | Timeout | Library |
|--------|------|---------|---------|
| Web search | `web` | 12s | Tavily → DuckDuckGo fallback |
| Wikipedia | `wiki` | 10s | `WikipediaLoader` |
| arXiv | `arxiv` | 12s | `arxiv.Client` |
| Semantic Scholar | `scholar` | 25s | `semanticscholar` |
| GitHub | `github` | 20s | `PyGithub` |
| Hacker News | `hn` | 10s | Algolia HN API |
| Stack Overflow | `so` | 15s | `stackapi.StackAPI` |
| Reddit | `reddit` | 15s | Tavily (site:reddit.com) |
| YouTube | `youtube` | 15s search + 10s transcript + 25s summary per video | `youtube-search` + transcript |
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

- [Installation](Installation.md)
- [Configuration](Configuration.md)
- [Architecture and Data Flow](Architecture-and-Data-Flow.md)
- [Research Sources](Research-Sources.md)
- [RAG Pipeline](RAG-Pipeline.md)
- [Personas and Depth Modes](Personas-and-Depth-Modes.md)
- [Database and Sessions](Database-and-Sessions.md)
- [MCP Server](MCP-Server.md)
- [Development Guide](Development-Guide.md)
- [Adding a New Source](Adding-a-New-Source.md)

## Key Layout

```
src/
├── agent.py                 LangGraph graph definition (9 nodes, conditional edges)
├── state.py                 AgentState TypedDict (32 fields)
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
    ├── router_tools.py      LLM planning, fact-check evaluation
    ├── chat_tools.py        Conversational follow-up node
    └── translation_tools.py Multilingual query expansion

tests/
knowledge_base/             Local files for RAG (PDF, TXT)
reports/                    Generated output files
```

## Non-Obvious Facts

- **YouTube runs sequentially within its thread** — transcript summarization depends on search results, so `search_videos_node` and `summarize_videos_node` run in series inside one thread.
- **`news_editor` and `quick` depth skip quality evaluation** — the fact-check evaluation is bypassed entirely; immediacy takes priority over depth.
- **No automatic re-plan**: `evaluate_research_node` always returns `next_node = "END"`; factually dubious claims are appended to the report as a warning. The `evaluate_research -> plan_research` edge exists in the graph but is currently never taken.
- **Cross-session memory**: each completed research is stored in ChromaDB collection `session_memory`. The planner retrieves up to 3 semantically similar past sessions to avoid re-investigating the same ground.
- **Word count and reading time** are shown in every report (200 words/min estimate).
- **Email is idempotent** — an MD5 hash of the report content is stored in state; if `last_email_hash` matches, the send is skipped.
- **Thread-safe results use container dicts** — each source function writes to `container = {"data": []}` inside its thread rather than returning a value; the main thread reads after `join(timeout=X)`.
- **LLM synthesis timeout is 6 minutes** — hard-coded `timeout=360` in `synthesis_tools.py`; this is the single longest operation.
- **Local RAG is opt-in** — not checked by default in the Streamlit sidebar; user must enable "Include local knowledge base".
- **Source reliability scores embedded in context** — 1–5 scores per source type are passed to the LLM during synthesis (local_rag/wiki/arxiv = 5, reddit = 2).
