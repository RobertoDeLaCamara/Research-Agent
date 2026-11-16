# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Web and Reddit search use DuckDuckGo (`ddgs`) only; Tavily is removed (3 attempts, retries drop the time limit).
- The dead `evaluate_research -> plan_research` edge is gone: the fact-check never re-plans, and `evaluate_research`
  goes straight to `generate_report`.
- `local_rag` also searches an external books library (`BOOKS_RAG_URL`); local knowledge is capped at
  `LOCAL_CONTEXT_MAX_CHARS` (7500) of the synthesis context so web and arXiv results are not pushed out.
- OpenAI-compatible backends get `max_tokens` (Ollama-only kwargs are dropped), so the output cap applies on DeepSeek.
- Uploads enforce `MAX_FILE_SIZE_MB` and `ALLOWED_FILE_EXTENSIONS` and keep only the base name of the file
  (a `../` in the client file name could write outside the knowledge base). The unused `thread_execution_timeout`
  and `max_content_length` settings were removed.
- Relevance filters for books, arXiv and Reddit hits; bot-block / CAPTCHA pages and ad redirects are discarded;
  the fact-checker receives a digest of the source excerpts; reports cut by the token cap are trimmed only when
  the model reports `finish_reason`/`done_reason` = `length`.

### Removed
- The unused settings `MAX_RESULTS_PER_SOURCE`, `MAX_CONCURRENT_REQUESTS`, `REQUEST_TIMEOUT` and `CACHE_EXPIRY_HOURS`
  (no code read them; results per source follow the research depth). Leftover values in `.env` are ignored.

### Documentation
- Corrected test counts, coverage figures, timeouts and examples against the code.

### Security
- API keys and the model a visitor enters in the UI are now scoped to that visitor's session. They were written
  to `os.environ`, which every session of the server shares: on a public deployment one visitor's key was used
  by, and pre-filled in the key fields of, everyone else. A server-side key is no longer sent to the browser as
  the value of its (disabled) field. See `src/credentials.py`.

### Added
- Hybrid local RAG (`RAG_MODE=hybrid`): ChromaDB dense search + SQLite FTS5/BM25 fused with RRF, returning the
  best chunks with book and page instead of whole files; `python -m src.tools.rag_index` builds and updates the
  index (incremental, replaces changed files, skips table-of-contents/garbled chunks). Default stays `legacy`.
  The semantic path had been dropped from `local_rag_node` in the 2026-04-06 merge (`824df11`); this restores it.
- `scripts/eval_retrieval.py`: dense vs keyword vs hybrid recall/MRR with paired bootstrap confidence intervals.
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
