# Development Guide

## Prerequisites

- Python 3.10+
- Ollama with `qwen3:14b` pulled (`ollama pull qwen3:14b`)
- Optional: Tavily API key (`TAVILY_API_KEY`), GitHub token (`GITHUB_TOKEN`)

## Setup

```bash
# Docker (recommended)
docker compose up -d
# Access Streamlit: http://localhost:8501
# Pull model first if needed:
docker compose exec ollama ollama pull qwen3:14b

# Local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: OLLAMA_BASE_URL, TAVILY_API_KEY, GITHUB_TOKEN, etc.

streamlit run src/app.py --server.address=0.0.0.0
# or CLI:
python src/main.py "Your Research Topic"
python src/main.py "Topic" --log-level DEBUG
python src/main.py "Topic" --skip-health-check
```

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
pytest tests/test_research_tools.py::test_search_web_node -v
pytest tests/ -x          # stop on first failure
pytest tests/ --lf        # re-run last failed
pytest tests/ -n auto     # parallel
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `qwen3:14b` | Model name |
| `TAVILY_API_KEY` | No | — | Primary web search; DuckDuckGo used if absent |
| `GITHUB_TOKEN` | No | — | GitHub API rate limit (5000/h vs 60/h unauthenticated) |
| `OPENAI_API_KEY` | No | — | Optional OpenAI fallback |
| `EMAIL_HOST` | No | `smtp.gmail.com` | SMTP server |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_USERNAME` | No | — | SMTP user |
| `EMAIL_PASSWORD` | No | — | SMTP password (app-specific for Gmail) |
| `EMAIL_RECIPIENT` | No | — | Report destination email |
| `DB_PATH` | No | `research_sessions.db` | Session database path |
| `RAG_KB_DIR` | No | `./knowledge_base` | Local knowledge base directory |
| `LOG_LEVEL` | No | `INFO` | DEBUG/INFO/WARNING/ERROR |

## Adding a New Source

1. Add a fetch function in `src/tools/research_tools.py`:
   ```python
   def search_mysource_node(state: AgentState) -> dict:
       container = {"data": []}
       def fetch():
           # ... fetch logic
           container["data"] = results
       t = threading.Thread(target=fetch)
       t.start()
       t.join(timeout=20)
       return {"mysource_research": container["data"]}
   ```

2. Register in `parallel_tools.py`:
   ```python
   source_functions["mysource"] = search_mysource_node
   ```

3. Add the result field to `AgentState` in `state.py`:
   ```python
   mysource_research: List[dict]
   ```

4. Include in `synthesis_tools.py` context assembly.

5. Add to the Streamlit sidebar checkbox list in `app.py`.

## Available LLM Models (Streamlit Sidebar)

| Model | Description |
|-------|-------------|
| `qwen3:14b` | Default. Best balance of quality and speed |
| `qwen2.5:14b` | Alternative Qwen version |
| `gemma3:12b` | Google Gemma, good for technical topics |
| `llama3:8b` | Faster, less capable — good for quick depth |

Override via `OLLAMA_MODEL` env var or select in sidebar.

## Project Structure

```
src/
├── agent.py                 StateGraph: 9 nodes, conditional edges
├── state.py                 AgentState TypedDict (24 fields)
├── config.py                Pydantic Settings, all timeouts and limits
├── db_manager.py            SQLite sessions: save/load/clear/cleanup
├── app.py                   Streamlit: sidebar config, progress display,
│                            source explorer, download center, chat UI
├── main.py                  CLI: argparse, health checks, invoke graph
└── tools/
    ├── parallel_tools.py    ThreadPoolExecutor fan-out, futures_map
    ├── research_tools.py    10 source fetch functions (web/wiki/arxiv/...)
    ├── rag_tools.py         ChromaDB ingest, hybrid retrieval, progress
    ├── synthesis_tools.py   Ollama synthesis: persona prompts, output cleaning
    ├── reporting_tools.py   HTML/PDF/DOCX/MD rendering, sanitize_text()
    ├── router_tools.py      plan_research_node, evaluate_research_node,
    │                        route_evaluation(), route_chat()
    ├── chat_tools.py        chat_node, trigger detection
    └── translation_tools.py expand_queries_multilingual()

tests/
knowledge_base/             Place .pdf and .txt files here for RAG
reports/                    Generated outputs (gitignored)
data/
├── chroma_db/              ChromaDB persistence
├── rag_cache.db            RAG file cache
└── rag_status.json         RAG ingestion progress
```

## Key Timeout Reference

| Constant | Value | Location |
|----------|-------|----------|
| `web_search_timeout` | 45s | config.py |
| `llm_request_timeout` | 60s | config.py |
| `content_fetch_timeout` | 3s | config.py (Jina Reader per URL) |
| `thread_execution_timeout` | 30s | config.py |
| `synthesis_request_timeout` | 360s | config.py (6 min for LLM synthesis) |
| Wikipedia | 10s | research_tools.py |
| arXiv | 25s | research_tools.py |
| Semantic Scholar | 25s | research_tools.py |
| GitHub | 20s | research_tools.py |
| Hacker News | 10s | research_tools.py |
| Stack Overflow | 15s | research_tools.py |
| Reddit | 15s | research_tools.py |
| YouTube search | 15s | research_tools.py |
| YouTube transcript | 20s | research_tools.py |
| YouTube summarization | 90s/video | research_tools.py |

## CI/CD

Jenkins pipeline targets `192.168.1.86:5000` (private registry). SonarQube integration via `sonar-project.properties`. Stages: lint → test → build → push → deploy.

## Debugging

**Slow synthesis:** Increase Ollama resources or switch to `llama3:8b` for faster (less thorough) synthesis.

**Source returning no results:** Check API key configuration. Tavily requires `TAVILY_API_KEY`; without it, DuckDuckGo is used for web and Reddit.

**ChromaDB errors on startup:** Delete `/app/data/chroma_db/` and restart — it will be rebuilt on next RAG query.

**LangGraph recursion limit exceeded:** The graph has `recursion_limit=100`. If hit, check that `iteration_count` is properly incremented and the exit condition (`>= 2`) is working.
