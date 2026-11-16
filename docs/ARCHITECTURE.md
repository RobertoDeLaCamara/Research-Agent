# Architecture Overview

## System Design

The Research-Agent is built on **LangGraph**, a framework for creating stateful, multi-actor applications with LLMs. The system runs a **single-pass autonomous workflow**: plan, search all sources in parallel, synthesize, fact-check, report.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Dashboard                      │
│                    (User Interface)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐          │
│  │  Router  │───▶│ Research │───▶│  Synthesis   │          │
│  │  Tools   │    │  Tools   │    │    Tools     │          │
│  └──────────┘    └──────────┘    └──────────────┘          │
│       │               │                   │                  │
│       └───────────────┴───────────────────┘                  │
│                       │                                      │
│                       ▼                                      │
│              ┌─────────────────┐                            │
│              │  Evaluation     │                            │
│              │  (fact-check)   │                            │
│              └─────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  • Ollama (LLM)    • DuckDuckGo (Web) • GitHub              │
│  • arXiv           • Semantic Scholar • Reddit              │
│  • YouTube         • Stack Overflow   • Hacker News         │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. State Management (`src/state.py`)

**AgentState** - TypedDict containing all workflow state:
- Research inputs (topic, depth, persona)
- Research results (web, wiki, arxiv, etc.)
- Synthesis outputs (consolidated_summary, report)
- Control flow (`next_node`, `iteration_count`; there is no re-plan loop)

### 2. Router Tools (`src/tools/router_tools.py`)

**Responsibilities:**
- `plan_research_node`: Analyzes topic and selects appropriate sources
- `evaluate_research_node`: Fact-checks the synthesis and appends a warning for dubious claims (never triggers a re-plan; skipped for `quick` depth and the `news_editor` persona)
- `update_next_node`: Manages workflow navigation (used internally by search nodes)

**Key Logic:**
```python
def plan_research_node(state):
    # LLM analyzes topic → selects sources
    # Returns: research_plan = ["web", "arxiv", "github", ...]

def evaluate_research_node(state):
    # LLM evaluates completeness
    # Returns: next_node = "END" (currently always; dubious claims are appended as a warning)
```

### 2b. Parallel Tools (`src/tools/parallel_tools.py`)

**Responsibilities:**
- `parallel_search_node`: Executes all planned research sources concurrently using `ThreadPoolExecutor`
- `_youtube_combined_node`: Internal wrapper that runs YouTube search + summarize sequentially within one thread

**Key Logic:**
```python
def parallel_search_node(state):
    plan = state["research_plan"]  # e.g. ["web", "arxiv", "github"]
    # Maps each source to its function, executes all in parallel
    # Writes per-source progress to /tmp/parallel_search_status.json
    # Global 60s timeout via as_completed(timeout=60)
    # Returns combined results from all sources
```

### 3. Research Tools (`src/tools/research_tools.py`)

**Multi-Source Data Collection:**
- `search_web_node`: DuckDuckGo (`ddgs`) with Jina Reader enhancement
- `search_wiki_node`: Wikipedia summaries
- `search_arxiv_node`: Academic papers
- `search_scholar_node`: Semantic Scholar citations
- `search_github_node`: Code repositories
- `search_hn_node`: Hacker News discussions
- `search_so_node`: Stack Overflow Q&A

**Pattern:**
```python
def search_X_node(state: AgentState) -> dict:
    # 1. Extract query from state
    # 2. Call external API with timeout
    # 3. Parse and structure results
    # 4. Return: {X_research: [...], next_node: "..."}
```

### 4. Synthesis Tools (`src/tools/synthesis_tools.py`)

**Consolidation:**
- Combines all research sources
- Applies persona-specific analysis
- Generates bibliography
- Creates consolidated summary
- Output cap per depth: 4096 / 6144 / 8192 tokens (quick / standard / deep). If the model stops on the cap
  (`finish_reason` / `done_reason` = `length`), the broken last line is trimmed; complete reports are untouched.
- Source context is cut at `MAX_SYNTHESIS_CONTEXT_CHARS`; local knowledge goes first and is limited to `LOCAL_CONTEXT_MAX_CHARS`

**Persona System:**
- `general`: Balanced analysis
- `business`: ROI and market focus
- `tech`: Implementation details
- `academic`: Rigor and methodology
- `pm`: User needs and prioritization
- `news_editor`: Breaking news — 24h Reddit filter, skips evaluation node for speed

### 5. Reporting Tools (`src/tools/reporting_tools.py`)

**Export Formats:**
- PDF (FPDF)
- Word (python-docx)
- HTML (styled)
- Markdown

### 6. RAG Tools (`src/tools/rag_tools.py`)

**Local Knowledge Integration:**
- PDF parsing (pypdf, up to 50 pages/doc)
- Text file ingestion
- Semantic vector search via ChromaDB + `all-MiniLM-L6-v2` embeddings (`src/tools/vector_store.py`)
- Hybrid retrieval: semantic + SQLite keyword matching, merged and scored
- Optional external books library (`BOOKS_RAG_URL`): book chunks with book/page/chapter citations, combined with the knowledge base results
- Citation tracking

## Workflow Execution

### Phase 1: Planning
```
User Input → Initialize State → Plan Research
                                      ↓
                            Select Sources (LLM)
```

### Phase 2: Research (Parallel Execution)
```
Plan → parallel_search_node (ThreadPoolExecutor)
         ├── Web ──────┐
         ├── Wiki ─────┤
         ├── arXiv ────┤
         ├── Scholar ──┤
         ├── GitHub ───┤  All sources execute concurrently
         ├── HN ───────┤
         ├── SO ───────┤
         ├── Reddit ───┤
         ├── YouTube* ─┤  (*search + summarize run sequentially within thread)
         └── RAG ──────┘
                  ↓
         Combined results merged into state
```

### Phase 3: Synthesis
```
All Results → Consolidate (LLM) → Consolidated Summary + Bibliography
```

### Phase 4: Evaluation
```
Consolidated Summary + digest of source excerpts (max 8000 chars) → Evaluate (LLM) → Fact-check
                                              ↓
                          Dubious claims? → Warning appended to the summary
                          Always          → Generate Report
```

### Phase 5: Reporting & Persistence
```
generate_report → Export (PDF/Word/HTML/MD) → send_email → save_db → END
```

## Key Design Patterns

### 1. Fact-Check Without Re-Planning
```python
workflow.add_edge("consolidate_research", "evaluate_research")
workflow.add_edge("evaluate_research", "generate_report")
```
The evaluation node flags dubious claims as a warning in the report. It does not
send the graph back to planning: re-searching to verify invented claims only
propagated them.

### 2. Fail-Soft Strategy
```python
try:
    results = api_call()
except Exception as e:
    logger.error(f"Failed: {e}")
    results = []  # Return empty, don't crash
```

### 3. Thread-Safe Timeout Protection
```python
container = {"data": []}
def run_search():
    container["data"] = [...]  # Write to mutable container

thread = threading.Thread(target=run_search)
thread.start()
thread.join(timeout=settings.web_search_timeout)
if not thread.is_alive():
    results = container["data"]  # Only read after thread completes
# If thread is still alive, results stays empty (safe default)
```

### 4. Parallel Source Execution
```python
def parallel_search_node(state):
    plan = state["research_plan"]
    with ThreadPoolExecutor(max_workers=len(plan)) as executor:
        futures_map = {executor.submit(fn, state): name for name, fn in source_functions.items() if name in plan}
        try:
            for future in as_completed(futures_map, timeout=60):  # 60s global timeout
                combined.update(future.result())
                _write_status(done, running, total)  # live UI progress
        except TimeoutError:
            pass  # skip slow sources, don't fail
    combined["next_node"] = "END"
    return combined
```

## Data Flow

### State Updates
Each node returns a dictionary that **updates** the state:
```python
def search_web_node(state):
    results = search_web(state["topic"])
    return {
        "web_research": results,
        "next_node": update_next_node(state, "web")
    }
```

### Immutability
LangGraph merges returned dicts into state immutably:
```python
new_state = {**old_state, **node_output}
```

## Configuration

### Centralized Settings (`src/config.py`)
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # AI
    ollama_model: str = "qwen3:14b"

    # Performance
    web_search_timeout: int = 12

    # Security
    max_file_size_mb: int = 10
    allowed_file_extensions: List[str] = ['.pdf', '.txt']
```

### Research Depth Mapping
```python
depth_mapping = {
    "quick": 2 results,
    "standard": 5 results,
    "deep": 10 results
}
```

## Database Schema

### SQLite (`research_sessions.db`)
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    persona TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    state_json TEXT
);

-- Indexes
CREATE INDEX idx_sessions_timestamp ON sessions(timestamp DESC);
CREATE INDEX idx_sessions_topic ON sessions(topic);
```

## Performance Considerations

### Parallelization
- **Research sources**: All planned sources execute in parallel via `ThreadPoolExecutor` in `parallel_search_node`
- **Jina Reader calls**: ThreadPoolExecutor (5 workers) within web search
- **YouTube**: Search + summarize run sequentially within a single parallel thread

### Caching
- Source results are not cached.
- Local RAG keeps a JSON cache of extracted file text (`rag_cache.json`, keyed by mtime + size) and a Chroma/FTS5 index.

### Timeouts
- Web search: 12s
- LLM requests: 60s
- Content fetch: 3s
- Per-source thread joins: Wikipedia 10s, arXiv 12s, Stack Overflow 15s, Hacker News 10s (HTTP), Reddit 15s, GitHub 20s, Scholar 25s
- LLM synthesis: 360s (hard-coded in `synthesis_tools.py`)
- Parallel search fan-out: 60s overall

## Security Architecture

### Input Validation
```python
# Topic sanitization
topic = re.sub(r'[<>"\']', '', topic)

# File upload validation
allowed_extensions = {'.pdf', '.txt', '.md'}
max_size = 10MB
```

### SQL Injection Prevention
```python
# Parameterized queries
cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
```

### API Key Management
```python
# Environment variables only
github_token = os.getenv("GITHUB_TOKEN")
```

## Extension Points

### Adding New Research Sources
1. Create node function in `src/tools/research_tools.py`
2. Register it in `source_functions` dict in `src/tools/parallel_tools.py`
3. Add tests

### Adding New Personas
1. Add persona config in `src/tools/synthesis_tools.py` and `src/tools/router_tools.py`
2. Add its code to the `Literal[...]` in `src/validators.py`
3. Update UI labels in `src/app.py` and `src/i18n.py`
4. Document in `wiki/Personas-and-Depth-Modes.md`

### Adding New Export Formats
1. Add generator in `src/tools/reporting_tools.py`
2. Update UI export options
3. Add tests

## Technology Stack

- **Framework**: LangGraph (workflow), LangChain (LLM)
- **LLM**: Ollama (local) or any OpenAI-compatible API (OpenAI, Groq, Gemini, DeepSeek, ...), optional light tier on local Ollama
- **UI**: Streamlit
- **Database**: SQLite
- **Testing**: pytest
- **Deployment**: Docker, Docker Compose

## Monitoring & Observability

### Logging

Standard library `logging`, configured once by `src/utils.py:setup_logging()` (level from `--log-level` or `LOG_LEVEL`). Modules get their logger with `logging.getLogger(__name__)` and use short event-style messages:

```python
logger.info(f"arxiv_search_completed results_count={len(results)}")
logger.warning("github_search_failed", exc_info=e)
logger.error("smtp_authentication_failed")
```

### Metrics (Future)
- Research duration
- Source success rates
- LLM token usage
- Cache hit rates

---

**Last Updated:** February 14, 2026
