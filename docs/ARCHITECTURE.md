# Architecture Overview

## System Design

The Research-Agent is built on **LangGraph**, a framework for creating stateful, multi-actor applications with LLMs. The system follows a **self-correcting autonomous workflow** pattern.

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
│              │  Evaluation &   │                            │
│              │  Self-Correction│                            │
│              └─────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  • Ollama (LLM)    • Tavily (Web)    • GitHub              │
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
- Control flow (next_node, iteration_count)

### 2. Router Tools (`src/tools/router_tools.py`)

**Responsibilities:**
- `plan_research_node`: Analyzes topic and selects appropriate sources
- `evaluate_research_node`: Assesses quality and identifies gaps
- `update_next_node`: Manages workflow navigation (used internally by search nodes)

**Key Logic:**
```python
def plan_research_node(state):
    # LLM analyzes topic → selects sources
    # Returns: research_plan = ["web", "arxiv", "github", ...]

def evaluate_research_node(state):
    # LLM evaluates completeness
    # Returns: next_node = "plan_research" (gaps) or "END" (complete)
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
    # Returns combined results from all sources
```

### 3. Research Tools (`src/tools/research_tools.py`)

**Multi-Source Data Collection:**
- `search_web_node`: Tavily/DuckDuckGo with Jina Reader enhancement
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

**Persona System:**
- `general`: Balanced analysis
- `business`: ROI and market focus
- `tech`: Implementation details
- `academic`: Rigor and methodology
- `pm`: User needs and prioritization

### 5. Reporting Tools (`src/tools/reporting_tools.py`)

**Export Formats:**
- PDF (FPDF)
- Word (python-docx)
- HTML (styled)
- Markdown

### 6. RAG Tools (`src/tools/rag_tools.py`)

**Local Knowledge Integration:**
- PDF parsing (pypdf)
- Text file ingestion
- Vector search (future: embeddings)
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
Consolidated Summary → Evaluate (LLM) → Quality Check
                                              ↓
                                    Gaps Found? → Re-plan
                                    Complete?   → Generate Report
```

### Phase 5: Reporting
```
Report Generation → Export (PDF/Word/HTML/MD) → User Download
```

## Key Design Patterns

### 1. Self-Correction Loop
```python
workflow.add_conditional_edges(
    "evaluate_research",
    route_evaluation,
    {
        "plan_research": "plan_research",  # Loop back if gaps
        "END": "generate_report"            # Proceed if complete
    }
)
```

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
        futures = {executor.submit(fn, state): name
                   for name, fn in source_functions.items() if name in plan}
        for future in as_completed(futures):
            combined.update(future.result())
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
    max_results_per_source: int = 5
    web_search_timeout: int = 45

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
- File-based cache with TTL
- Cache key: hash(source + query)
- Expiry: 24 hours (configurable)

### Timeouts
- Web search: 45s
- LLM requests: 60s
- Content fetch: 3s
- Thread execution: 30s

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
tavily_api_key = os.getenv("TAVILY_API_KEY")
```

## Extension Points

### Adding New Research Sources
1. Create node function in `src/tools/research_tools.py`
2. Register it in `source_functions` dict in `src/tools/parallel_tools.py`
3. Add tests

### Adding New Personas
1. Add persona config in `src/tools/synthesis_tools.py`
2. Update UI in `src/app.py`
3. Document in `docs/PERSONAS.md`

### Adding New Export Formats
1. Add generator in `src/tools/reporting_tools.py`
2. Update UI export options
3. Add tests

## Technology Stack

- **Framework**: LangGraph (workflow), LangChain (LLM)
- **LLM**: Ollama (local), OpenAI (optional)
- **UI**: Streamlit
- **Database**: SQLite
- **Testing**: pytest
- **Deployment**: Docker, Docker Compose

## Monitoring & Observability

### Logging

Structured logging via `structlog` wrapping stdlib `logging`. All existing `logging.getLogger()` calls flow through structlog processors automatically.

- **Dev** (`ENV=dev`, default): Pretty console output via `ConsoleRenderer`
- **Production** (`ENV=production`): JSON output via `JSONRenderer`

Configuration: `src/logging_config.py`, called from `src/utils.py:setup_logging()`.

```python
logger.info("arxiv_search_completed", results_count=5)
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
