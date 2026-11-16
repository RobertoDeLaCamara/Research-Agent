# Configuration

All configuration is done through environment variables, read by `src/config.py` (Pydantic Settings). Copy `env.example` to `.env` and edit it.

## LLM backend

| Variable | Default in code | Description |
|----------|-----------------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of the LLM. Point it at a cloud endpoint to use Groq, Gemini, etc. |
| `OLLAMA_MODEL` | `qwen3:14b` | Model name; it must exist on the configured endpoint. |
| `OPENAI_API_KEY` | _(empty)_ | Required for any cloud endpoint. When set, `ChatOpenAI` is used instead of `ChatOllama`. |
| `DEEPSEEK_API_KEY` | _(empty)_ | DeepSeek shortcut: points the client at `https://api.deepseek.com` and, if the model is empty or a `qwen*` one, uses `deepseek-chat`. Takes precedence over `OPENAI_API_KEY`. |

Note: `env.example` and `docker-compose.full.yml` set `OLLAMA_MODEL` to `qwen2.5:1.5b` (about 1 GB) so the zero-config setup is light. The code default, `qwen3:14b`, gives better quality if you have the hardware.

### Cloud endpoint presets

```env
# Groq — free tier
OPENAI_API_KEY="gsk_..."
OLLAMA_BASE_URL="https://api.groq.com/openai/v1"
OLLAMA_MODEL="llama-3.1-8b-instant"

# Google Gemini — free tier
OPENAI_API_KEY="AIza..."
OLLAMA_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
OLLAMA_MODEL="gemini-1.5-flash"

# OpenAI
OPENAI_API_KEY="sk-..."
OLLAMA_BASE_URL="https://api.openai.com/v1"
OLLAMA_MODEL="gpt-4o-mini"
```

Ollama-only options (`repeat_penalty`, `num_ctx`, `reasoning`) are dropped for OpenAI-compatible endpoints. The output cap (`num_predict`) is sent as `max_tokens`: as a normal parameter to `api.openai.com`, and in the request body for other endpoints, because some of them (DeepSeek) ignore the `max_completion_tokens` field that `langchain-openai` sends.

### Light tier (optional)

Cheap steps (query expansion, source routing) can run on a small local model while the report is written by the main one. With `LIGHT_LLM_MODEL` unset, everything uses the main backend.

| Variable | Default | Description |
|----------|---------|-------------|
| `LIGHT_LLM_MODEL` | _(unset)_ | Ollama model for light steps, e.g. `qwen3.5:9b`. If a light call fails, it is retried once on the main backend. |
| `LIGHT_LLM_BASE_URL` | `http://localhost:11434` | Ollama server for the light model |
| `OLLAMA_REASONING` | `false` | Enables the thinking phase on reasoning models (qwen3.x). Off because it can take minutes and bypass the timeout. |

## Optional API keys

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub search (higher rate limits) |
| `YOUTUBE_API_KEY` | YouTube source (disabled if unset) |

Results per source are not configurable: they follow the research depth (Quick 2, Standard 5, Deep 10). There is no result cache. (`MAX_RESULTS_PER_SOURCE`, `MAX_CONCURRENT_REQUESTS`, `REQUEST_TIMEOUT` and `CACHE_EXPIRY_HOURS` were removed: nothing read them. If they are still in your `.env` they are ignored.)

The report's output cap is fixed by depth: 4096 (Quick), 6144 (Standard) or 8192 (Deep) tokens.

## Email delivery

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_HOST` | `smtp.gmail.com` | SMTP server |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USERNAME` | _(empty)_ | SMTP username |
| `EMAIL_PASSWORD` | _(empty)_ | SMTP password / app password |
| `EMAIL_RECIPIENT` | _(empty)_ | Address that receives the report |

## Performance and storage

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_SEARCH_TIMEOUT` | `12` | Seconds to wait for the web search thread |
| `LLM_REQUEST_TIMEOUT` | `60` | Timeout for an LLM call, in seconds |
| `CONTENT_FETCH_TIMEOUT` | `3` | Timeout for fetching a page's full text, in seconds |
| `MAX_CONTENT_PREVIEW_CHARS` | `5000` | Characters kept from a fetched page |
| `MAX_SYNTHESIS_CONTEXT_CHARS` | `25000` | Source text passed to the report writer |
| `LOCAL_CONTEXT_MAX_CHARS` | `7500` | Part of that budget for local knowledge (books, knowledge base); whole chunks, best first. `0` = no cap |
| `SYNTHESIS_NUM_CTX` | `16384` | Ollama context window for the report call. If it is too small, Ollama drops the start of the prompt (the instructions). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `DB_PATH` | `research_sessions.db` | SQLite file for saved sessions |

### Uploads

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE_MB` | `10` | Larger uploads are rejected with a warning and not saved |
| `ALLOWED_FILE_EXTENSIONS` | `[".pdf", ".txt"]` | Accepted upload types (JSON list). Only `.pdf` and `.txt` are read by `local_rag`. |

Uploaded files are saved under their base name in `RAG_KB_DIR`, so a client-supplied path cannot write elsewhere.

## Local knowledge (RAG)

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_MODE` | `legacy` | `legacy` (file scan) or `hybrid` (Chroma + BM25 chunks) |
| `RAG_TOP_K` | `8` | Chunks returned in `hybrid` mode and from the books library |
| `RAG_KB_DIR` | `./knowledge_base` | Folder of user documents |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma_db` | Hybrid index location |
| `RERANK_URL` | _(unset)_ | Optional cross-encoder reranker for the hybrid results |
| `BOOKS_RAG_URL` | _(unset)_ | Optional books search service, searched together with the knowledge base |
| `USE_RAG_DEFAULT` | on if `BOOKS_RAG_URL` set | Default of the "Include local knowledge base" checkbox |

All options and their behaviour: [RAG Pipeline](RAG-Pipeline.md).

## Chat

`RESEARCH_TRIGGER_KEYWORDS` (default: investiga, busca, más información, research, search, investigate) are the words that make a chat follow-up start a new research run instead of answering from the report.

## MCP server

`RESEARCH_AGENT_OUTPUT_ROOT` and `RESEARCH_AGENT_TIMEOUT` are read by `mcp_server.py`; see [MCP Server](MCP-Server.md).
