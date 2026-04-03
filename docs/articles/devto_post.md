---
title: Building a multi-source autonomous research agent with LangGraph, ThreadPoolExecutor and Ollama
published: false
description: Architecture deep-dive — parallel execution, self-correction loop, LLM factory, and the bugs I hit along the way.
tags: python, ai, langchain, opensource
---

I wanted a tool that could research any topic deeply — not just one web search, but Wikipedia, arXiv, Semantic Scholar, GitHub, Hacker News, Stack Overflow, Reddit, YouTube and local documents, all at once. So I built it.

This post covers the architecture decisions, the parallel execution model, the self-correction loop, and a few things that didn't work before I got it right.

**Live demo:** https://huggingface.co/spaces/ecerocg/research-agent  
**Source:** https://github.com/RobertoDeLaCamara/Research-Agent

---

## The problem with sequential research agents

Most agent examples I found do this:

```
search web → process → search wiki → process → search arxiv → process → synthesize
```

If each source takes 5–10 seconds (network + LLM processing), a 10-source agent takes 50–100 seconds minimum — before synthesis.

The fix is obvious: run everything in parallel.

---

## Architecture overview

```
initialize_state
      │
plan_research  ←──────────────────────┐
      │                               │
parallel_search                    re-plan
      │                               │
consolidate ──→ evaluate ─────────────┘
      │              │
   report          END
```

The graph is implemented with LangGraph's `StateGraph`. Each node receives the full `AgentState` TypedDict and returns a partial update.

---

## Parallel execution with ThreadPoolExecutor

The core of the agent is `parallel_search_node`:

```python
def parallel_search_node(state: AgentState) -> dict:
    source_functions = {
        "web":       search_web_node,
        "wiki":      search_wiki_node,
        "arxiv":     search_arxiv_node,
        "scholar":   search_scholar_node,
        "github":    search_github_node,
        "hn":        search_hn_node,
        "so":        search_so_node,
        "reddit":    search_reddit_node,
        "local_rag": local_rag_node,
        "youtube":   _youtube_combined_node,
    }

    plan = state.get("research_plan", [])
    combined = {}
    futures_map = {}

    with ThreadPoolExecutor(max_workers=len(plan) or 1) as executor:
        for source_name in plan:
            fn = source_functions.get(source_name)
            if fn:
                future = executor.submit(fn, state)
                futures_map[future] = source_name

        for future in as_completed(futures_map):
            source_name = futures_map[future]
            try:
                result = future.result()
                combined.update(result)
            except Exception as e:
                logger.error(f"Source '{source_name}' failed: {e}")

    return combined
```

Each source function is independent and returns a partial state dict. `combined.update(result)` merges all results — no locking needed because each source writes to different state keys.

**YouTube is an exception** — search must complete before summarize can run, so it gets a sequential wrapper inside the parallel executor:

```python
def _youtube_combined_node(state: AgentState) -> dict:
    search_result = search_videos_node(state)
    merged_state = {**state, **search_result}
    summarize_result = summarize_videos_node(merged_state)
    combined = {}
    combined.update(search_result)
    combined.update(summarize_result)
    return combined
```

This brings total research time from ~5 min sequential to ~45s on a decent connection.

---

## The self-correction loop

After parallel search, an evaluation node checks for knowledge gaps:

```python
def evaluate_research_node(state: AgentState) -> dict:
    iteration = state.get("iteration_count", 0)

    if iteration >= 2:
        return {
            "next_node": "END",
            "evaluation_report": "Max iterations reached."
        }

    llm = get_llm(temperature=0.1)
    response = llm.invoke([HumanMessage(content=prompt)])

    if gaps_detected(response):
        return {
            "next_node": "re_plan",
            "iteration_count": iteration + 1
        }
    return {"next_node": "END"}
```

The LangGraph conditional edge routes back to `plan_research` or forward to `END`:

```python
workflow.add_conditional_edges(
    "evaluate_research",
    lambda state: state.get("next_node", "END"),
    {
        "re_plan":  "plan_research",
        "END":      "consolidate_research"
    }
)
```

On re-plan, the LLM can select different or additional sources based on what was missing. On niche topics this second pass noticeably improves coverage.

---

## Dynamic research planning with personas

Before searching, `plan_research_node` asks the LLM which sources are relevant for the topic. This avoids wasting API calls on irrelevant sources.

Five personas shape the planning:

| Persona | Focus |
|---|---|
| Generalist | Balanced across all sources |
| Software Architect | GitHub, HN, SO heavily weighted |
| Market Analyst | Web, Reddit, HN |
| Scientific Reviewer | arXiv, Semantic Scholar |
| Product Manager | Web, Reddit, YouTube |

The persona prompt changes what the LLM considers "relevant", so the research plan — and therefore which threads run in parallel — differs per persona.

---

## LLM factory: local or cloud with zero config changes

```python
def get_llm(temperature: float = 0, timeout: int = None):
    api_key  = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model    = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

    if api_key or _is_cloud_endpoint(base_url):
        return ChatOpenAI(
            api_key=api_key or "ollama",
            base_url=base_url,
            model=model,
            temperature=temperature,
            timeout=timeout,
        )
    else:
        return ChatOllama(
            base_url=base_url,
            model=model,
            temperature=temperature,
        )
```

The same agent code runs against local Ollama or Groq/Gemini/OpenAI — just swap env vars. Reads `os.environ` at call time (not at import) so Streamlit sidebar overrides work without restart.

---

## What didn't work

**`nonlocal` in threaded callbacks** — I originally used `nonlocal` to capture results from threads. Race conditions appeared under load. Fixed by switching to a mutable container pattern (`container = {"data": []}`) and reading only after `thread.join()`.

**Pydantic v1 validators** — `@validator` with positional `cls` broke on Pydantic v2. Migrated to `@field_validator` with `@classmethod`.

**Sequential YouTube** — the first version treated YouTube like other sources. Summarization needs the transcript, which needs the video URL, which needs the search. Making it a composed sequential node within the parallel executor fixed this.

**`.env` baked into Docker image** — `COPY . .` was copying `.env` into the image, leaking credentials. Added `.env` to `.dockerignore`. Docker Compose also interpolates `${OLLAMA_MODEL:-default}` from `.env`, which overrode the intended demo model. Hardcoded the values in `docker-compose.full.yml` instead.

---

## Running it locally

```bash
# With local Ollama — no API keys needed:
git clone https://github.com/RobertoDeLaCamara/Research-Agent
cd Research-Agent
docker compose -f docker-compose.full.yml up
# pulls qwen2.5:1.5b automatically, starts at localhost:8501

# With Groq free tier:
cp env.example .env
# OPENAI_API_KEY=your_groq_key
# OLLAMA_BASE_URL=https://api.groq.com/openai/v1
# OLLAMA_MODEL=llama-3.1-8b-instant
docker compose up
```

---

## What's next

- Streaming output so the UI updates as each source completes
- Better synthesis prompts for small models (1.5b demo)
- Persistent research sessions with diff between iterations

---

**Live demo:** https://huggingface.co/spaces/ecerocg/research-agent  
**Source:** https://github.com/RobertoDeLaCamara/Research-Agent

Happy to answer questions about any part of the architecture.
