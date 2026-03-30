# Research-Agent

LangGraph-based autonomous research agent. 5 personas, multi-source RAG, Streamlit UI. LangChain + Ollama/OpenAI, Tavily, ChromaDB.

## Key Commands

```bash
streamlit run src/app.py

python -m pytest tests/ -v   # 37 tests, 100% pass rate

docker compose up -d          # volume mounts for live reload
```

## CI — Jenkins Build #6

- Multibranch pipeline, GiteaSCMSource
- Gitea webhook #4 → `http://192.168.1.86:8088/gitea-webhook/post` (working)

## Key Files

- `src/app.py` — Streamlit entry point
- `src/agent.py` — LangGraph agent
- `src/config.py` — configuration
- `src/tools/` — research, RAG, Reddit, YouTube, parallel tools
- `src/validators.py`

## Remotes

- `origin` → Gitea (192.168.1.62:9090/roberto/research-agent)
- `github` → GitHub (RobertoDeLaCamara/Research-Agent)
- License: MIT
