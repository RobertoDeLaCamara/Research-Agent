# Configuration

All configuration is done through environment variables, read by `src/config.py` (Pydantic Settings). Copy `env.example` to `.env` and edit it.

## LLM backend

| Variable | Default in code | Description |
|----------|-----------------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of the LLM. Point it at a cloud endpoint to use Groq, Gemini, etc. |
| `OLLAMA_MODEL` | `qwen3:14b` | Model name; it must exist on the configured endpoint. |
| `OPENAI_API_KEY` | _(empty)_ | Required for any cloud endpoint. When set, `ChatOpenAI` is used instead of `ChatOllama`. |

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

## Optional API keys

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Tavily web search (falls back to DuckDuckGo if unset) |
| `GITHUB_TOKEN` | GitHub search (higher rate limits) |
| `YOUTUBE_API_KEY` | YouTube source (disabled if unset) |

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
| `MAX_RESULTS_PER_SOURCE` | `5` | Results per source (Quick uses 2, Standard 5, Deep 10) |
| `MAX_CONCURRENT_REQUESTS` | `5` | Concurrency of the thread pool |
| `CACHE_EXPIRY_HOURS` | `24` | How long source results are cached |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `DB_PATH` | `research_sessions.db` | SQLite file for saved sessions |

## MCP server

`RESEARCH_AGENT_OUTPUT_ROOT` and `RESEARCH_AGENT_TIMEOUT` are read by `mcp_server.py`; see [MCP Server](MCP-Server.md).
