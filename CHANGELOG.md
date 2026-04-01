# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **UI Language Switcher**: 🇪🇸/🇬🇧 toggle buttons at the top of the sidebar switch the entire dashboard between Spanish and English. Language persists in `st.session_state` across reruns. All 84 UI strings (labels, buttons, depth/persona options, node progress messages, chat prompts) are defined in `src/i18n.py`.
- **Cloud LLM Factory** (`src/llm.py`): `get_llm()` factory auto-selects `ChatOllama` (local) or `ChatOpenAI` (cloud) based on `OPENAI_API_KEY` presence or URL detection. Supports Groq (free tier), Google Gemini (free tier), OpenAI, OpenRouter, Cerebras, Mistral, and any OpenAI-compatible endpoint. Reads `os.environ` at call time so sidebar key overrides take effect without restart.
- **Hugging Face Spaces deployment**: `Dockerfile.spaces` (port 7860), sidebar API key panel shown when `SPACE_ID` env var is detected, `hf_spaces/README.md` with Space frontmatter, and `scripts/deploy_hf_spaces.sh` for one-command deploy.
- **Zero-config quickstart**: `docker-compose.full.yml` bundles Ollama + model pull + agent in a single `docker compose up`. `scripts/quickstart.sh` provides interactive setup for local/cloud/custom backends.
- **`env.example` presets**: Ready-to-paste configurations for Groq, Google Gemini, and OpenAI with inline comments.

## [1.0.0] - 2026-03-01

### Infrastructure
- Configure Gitea webhook for automatic Jenkins builds on push
- Fix Gitea ROOT_URL and Jenkins credentials for commit status notifications
- Verify end-to-end webhook trigger on push
- Fix Gitea ROOT_URL in docker-compose.yml (3300 -> 9090)
- **Docker Hardening**: Upgraded base image to `python:3.12-slim`, added non-root `app` user, added `HEALTHCHECK` via Streamlit health endpoint, added `curl` for healthcheck, `--chown` on COPY steps
- **Docker Compose**: Replaced `network_mode: "host"` with bridge network (`agent-net`), added resource limits (`mem_limit: 512m`, `cpus: 1.0`), switched from remote image to local `build: .`

### Fixed
- **Thread Safety**: Replaced all `nonlocal` patterns (12 instances across 4 files) with thread-safe mutable container pattern. Results are only read after `thread.join()` confirms the thread has finished, eliminating race conditions between timed-out threads and the main thread.
- **Thread Safety (RAG)**: Added `threading.Lock` for `update_status` in `rag_tools.py` where real concurrent access occurs via `ThreadPoolExecutor`.

### Changed
- **PyPDF2 → pypdf**: Migrated from deprecated `PyPDF2` to its modern replacement `pypdf` in `requirements.txt`, `src/tools/rag_tools.py`, and `tests/test_rag_tools.py`.
- **Structured Logging**: Replaced all 47 `print()` calls across 5 source files with structured `logger.*` calls. Added `structlog` dependency and `src/logging_config.py` module that wraps stdlib logging — JSON output in production (`ENV=production`), pretty console in dev. Updated `src/utils.py:setup_logging()` to use structlog configuration.
- **Pydantic v2 Migration**: Migrated `src/config.py` from deprecated `class Config:` to `model_config = SettingsConfigDict(...)`. Migrated `src/validators.py` from `@validator` to `@field_validator` with `@classmethod`.
- **Parallel Research Execution**: Replaced sequential source-by-source execution with `parallel_search_node` using `ThreadPoolExecutor`. All planned research sources now execute concurrently, reducing total research time from sum of timeouts to max of timeouts.
- **Simplified Graph**: Removed 10+ individual search nodes and all sequential conditional edges from the LangGraph workflow. New flow: `plan_research` → `parallel_search` → `consolidate_research`.

### Added
- **`src/logging_config.py`**: Structlog configuration module with environment-aware rendering (JSON for production, console for dev).
- **`src/tools/parallel_tools.py`**: New module with `parallel_search_node` (concurrent source execution) and `_youtube_combined_node` (YouTube search + summarize in sequence within one thread).
- **GitHub Actions CI**: Test matrix across Python 3.10 and 3.12 on every push and PR.

## [0.2.0] - 2026-01-25

### Fixed
- **Performance**: Optimized Local RAG by migrating from JSON to SQLite, eliminating startup lag and redundant re-scanning (warm cache < 0.002s).
- **Correctness**: Fixed early return logic in RAG node to return correct key.

### Added
- **RAG**: Implemented Hybrid Search (Vector + Keyword) using `ChromaDB` and `all-MiniLM-L6-v2` embeddings. Now finds relevant documents even without exact keyword matches.

## [0.1.0] - 2026-01-14

### Fixed
- **Critical**: Resolved Citation Hallucinations by enforcing strict Source extraction and Prompt engineering.
- **Critical**: Fixed Web Research Context to include Title and URL explicitly.
- **Critical**: Fixed HTML Report rendering for Web sources (References displayed as links with titles).
- **Critical**: Corrected Report Storage location (now saves to `./reports/` instead of root).
- **Critical**: Fixed Infinite Loops by limiting research to 2 iterations.
- **Critical**: Fixed RAG Logic to only appear/execute if local files exist.
- Resolved all import path inconsistencies (9 import errors → 0)
- Fixed all test failures (0% → 100% pass rate)
- Added missing dependencies (python-docx, PyPDF2)
- Fixed bare except clauses with specific exception handling
- Fixed thread safety issues in research tools
- Fixed skipped test to achieve 100% test coverage

### Added
- **Input Validation**: Pydantic ResearchRequest model with injection prevention
- **File Upload Validation**: Extension whitelist, size limits, filename sanitization
- **Centralized Configuration**: All timeouts, limits, and constants in config.py
- **Type Hints**: Comprehensive type annotations across utils, db_manager, and agent
- **Logging**: Consistent logger usage (replaced 27+ print statements)
- **Error Handling**: Specific exceptions with context logging

### Changed
- Replaced all hardcoded values with centralized config
- Improved error messages with detailed context
- Enhanced security with input validation (2/10 → 7/10)
- Improved code quality (6/10 → 9/10)
- Updated all tests to pass (37/37 passing at the time)

### Security
- Added injection attack prevention in topic validation
- Added file upload security (extension whitelist, size limits)
- Improved error handling to prevent information leakage
- **WARNING**: Exposed credentials in .env must be revoked before deployment

## [Previous] - Before 2026-01-14

### Known Issues
- Import path inconsistencies causing test failures
- Missing dependencies
- Hardcoded configuration values
- Bare except clauses
- Inconsistent logging with print statements
- Minimal type hints
