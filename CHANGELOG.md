# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MCP server 1.1.0: `start_research` / `get_research_result` background jobs, `depth`, `persona`, `lang`,
  `include_report` and sandboxed `output_dir` export (with YAML frontmatter) under `RESEARCH_AGENT_OUTPUT_ROOT`.
- CLI flags `--depth` and `--persona` in `src/main.py`.
- Deployment to Hugging Face Spaces (`docker-compose.full.yml`, `Dockerfile` on port 7860).
- Bilingual UI (Spanish / English) switcher in the sidebar (`src/i18n.py`).
- News Editor persona (`news_editor`) for breaking-news research with 24h Reddit filtering.
- Semantic RAG via ChromaDB + `all-MiniLM-L6-v2` embeddings (`src/tools/vector_store.py`).
- OpenAI-compatible LLM backend support (Groq, Gemini, OpenAI, LM Studio, Together, OpenRouter).

### Fixed
- MCP server: the timeout error reported 180 s while the real limit was 420 s; the limit is now configurable
  (`RESEARCH_AGENT_TIMEOUT`, default 900 s) and reported accurately. The full Markdown report is returned
  instead of a 3000-char preview, and the report is located by modification time instead of a fragile
  topic-derived filename.
- Report rendering in the UI and in the saved HTML file; the report is generated in the language selected in the UI.
- CI: the pipeline runs on `agent-45` (registry push failed from the built-in node) and retries `docker push` up to 3 times.

### Changed
- LangGraph workflow consolidated into `src/agent.py` (9 nodes, conditional re-plan edge).
- Report generation centralized in `src/tools/reporting_tools.py` (PDF, DOCX, Markdown, HTML).
- YouTube transcript fetcher now handles transcript blocks with fallback timeouts.
- Default Docker port aligned with Hugging Face Spaces (7860).

### Fixed
- Citation hallucinations — sources and URLs are now passed verbatim to the synthesis prompt.
- Infinite re-plan loops — capped at 2 iterations via conditional edges in `agent.py`.
- Report output location — reports saved to `./reports/` (mounted volume).
- RAG pipeline only runs when local files exist.
- Thread-safety of parallel research tools (container-based result capture).

### Security
- Input validation via Pydantic `ResearchRequest` model (injection prevention).
- File upload whitelist (`.pdf`, `.txt`, `.md`), 10 MB size cap, filename sanitization.
- Parameterized SQLite queries; no user input interpolated into SQL.
