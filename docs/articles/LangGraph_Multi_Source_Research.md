# Building a Self-Correcting Research Agent with LangGraph

Automated research tools face a recurring problem: any single source is incomplete, and most aggregation systems don't know when they've gathered enough. This article describes how the research-agent addresses both problems — parallel fan-out across 10 sources and a self-correction loop that re-searches when quality evaluation finds gaps.

---

## Why LangGraph Instead of a Simple Pipeline

The naive approach to multi-source research is a linear pipeline: search Wikipedia, search arXiv, search GitHub, concatenate results, call LLM. This works for simple cases but breaks down when you need:

1. **Conditional re-planning** — if the LLM's quality check finds shallow coverage, you need to loop back to search with adjusted source selection
2. **Routing based on dynamic state** — the `news_editor` persona should skip the re-evaluation step; the `academic` persona should never skip it
3. **Message history for chat** — following up on a completed research session requires carrying the synthesized findings as context

LangGraph models the agent as a `StateGraph` where each node receives the full state and returns partial updates. The graph can loop, branch, and terminate based on evaluated conditions — not just sequential execution.

```python
# The 9-node graph
workflow = StateGraph(AgentState)
workflow.add_node("initialize_state", initialize_state_node)
workflow.add_node("plan_research", plan_research_node)
workflow.add_node("parallel_search", parallel_search_node)
workflow.add_node("consolidate_research", consolidate_research_node)
workflow.add_node("evaluate_research", evaluate_research_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("send_email", send_email_node)
workflow.add_node("save_db", save_db_node)
workflow.add_node("chat", chat_node)

workflow.add_conditional_edges(
    "evaluate_research",
    route_evaluation,
    {"plan_research": "plan_research", "END": "generate_report"}
)
```

State updates are immutable dict merges — nodes return only the fields they modify, and LangGraph merges the partial update into the full state. Never mutate the state dict in-place inside a node.

---

## Parallel Fan-out with ThreadPoolExecutor

The `parallel_search` node executes all selected sources concurrently. Each source gets one thread, and results are collected as they complete:

```python
def parallel_search_node(state: AgentState) -> dict:
    plan = state["research_plan"]
    max_workers = len(plan) or 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures_map = {
            executor.submit(source_functions[source], state): source
            for source in plan
            if source in source_functions
        }

        for future in as_completed(futures_map):
            source_name = futures_map[future]
            try:
                result = future.result()
                # Merge result into accumulated state
                for key, value in result.items():
                    accumulated_state[key] = value
            except Exception as e:
                logger.error(f"Source {source_name} failed: {e}")
```

A failed source logs an error and continues — partial results are always better than a complete failure.

The one exception is YouTube. Because transcript summarization depends on the video URLs returned by search, both steps must run in series inside the same thread:

```python
def _youtube_combined_node(state: AgentState) -> dict:
    video_state = search_videos_node(state)        # → video_urls
    merged = {**state, **video_state}
    summary_state = summarize_videos_node(merged)  # → summaries
    return {**video_state, **summary_state}
```

---

## Timeout-Safe Execution Pattern

External APIs can hang indefinitely. Rather than relying on library-level timeouts (which are inconsistent across libraries), every source function uses Python's `threading.Thread` with an explicit `join(timeout=N)`:

```python
def search_arxiv_node(state: AgentState) -> dict:
    container = {"data": []}

    def fetch():
        client = arxiv.Client()
        search = arxiv.Search(query=topic, sort_by=arxiv.SortCriterion.Relevance)
        container["data"] = [
            {"title": r.title, "summary": r.summary,
             "authors": [a.name for a in r.authors], "url": r.entry_id}
            for r in client.results(search)
        ][:max_results]

    t = threading.Thread(target=fetch, daemon=True)
    t.start()
    t.join(timeout=25)  # 25 seconds hard cap

    return {"arxiv_research": container["data"]}
```

The container dict pattern (writing results to a shared dict rather than returning from the thread) is necessary because `threading.Thread` does not have a return value mechanism. After `join()` returns (either by completion or timeout), `container["data"]` contains whatever was written before the timeout.

If the thread hasn't finished when `join()` returns, the daemon thread continues running until the process exits but its partial results are discarded. This is acceptable for research — a partial arXiv result set is better than blocking the entire fan-out.

---

## Self-Correction: Re-plan, Don't Just Retry

When `evaluate_research_node()` finds the synthesis shallow or incomplete, the standard response would be to retry the same search with the same sources. This misses the point: if arXiv returned limited results on the first pass, querying arXiv again won't help.

Instead, the re-plan step gives the LLM the evaluation report as context and asks it to select sources again:

```python
# evaluate_research returns
{
  "sufficient": false,
  "gaps": ["no implementation examples", "missing recent benchmarks"],
  "shallow_topics": ["hardware requirements"],
  "fact_check_queries": ["verify GPU memory requirement claim"]
}

# plan_research receives this context in the next iteration
# and may select "github" and "hn" instead of "arxiv" and "wiki"
```

The cap at 2 iterations is not arbitrary — it prevents infinite loops when the topic is genuinely under-researched and no number of searches will produce a "sufficient" evaluation.

The `news_editor` persona bypasses evaluation entirely. Breaking news contexts prioritize speed; asking the LLM whether the synthesis is "academically rigorous" is a category error for that use case.

---

## Source Reliability as Context

The synthesis prompt doesn't treat all sources equally. Each source has a hardcoded reliability score (1–5) that is included in the LLM context:

```
Source reliability context:
- local_rag: 5/5 (user-curated knowledge base)
- arxiv: 5/5 (peer-reviewed)
- github: 4/5 (code-backed community)
- reddit: 2/5 (informal opinion)
```

This nudges the LLM to hedge claims sourced from Reddit ("community reports suggest...") and to assert with more confidence claims from arXiv ("studies demonstrate..."). The scores are fixed per source type — not computed dynamically from result quality.

---

## Email Idempotence

The send_email node runs after every successful research session. Without idempotence, re-loading a session from history and clicking "send report" would re-deliver an already-delivered email.

```python
report_hash = hashlib.md5(report.encode('utf-8')).hexdigest()
if state.get("last_email_hash") == report_hash:
    return {}  # No state update, no send

# Send, then persist the hash
return {"last_email_hash": report_hash}
```

The hash is stored in AgentState and persisted to SQLite with the session. When a session is loaded from history, the hash comes with it. If the report hasn't changed (same synthesis, same content), the email is skipped.

---

## Multilingual Query Expansion

Before fan-out, the planning step expands the research topic to multiple languages. Most sources can search in multiple languages, and a query in the native language of a topic community often returns different (and better) results:

```python
# Input: "inteligencia artificial en educación"
# Output:
queries = {
    "es": "inteligencia artificial en educación",
    "en": "artificial intelligence in education"
}
```

Source functions choose the appropriate language: Wikipedia auto-detects; GitHub defaults to English; web search uses the expanded queries as separate search terms.

---

## Output Pipeline

A single AgentState produces four output formats from the same synthesized content:

| Format | File | Library |
|--------|------|---------|
| HTML | `reports/reporte_final.html` | f-strings + CSS variables |
| Markdown | `reports/reporte_{topic}.md` | Markdown conversion |
| DOCX | `reports/reporte_final.docx` | python-docx |
| PDF | `reports/reporte_investigacion.pdf` | FPDF |

The PDF path uses Helvetica (standard FPDF font) and ASCII encoding with `ignore` errors — emoji and special characters are dropped. The HTML version has full Unicode support and includes interactive source badges and back-to-top links. Use HTML for reading; use PDF only for archival or printing requirements.

---

## Implementation Reference

| Component | File | Key Function |
|-----------|------|--------------|
| Graph definition | `src/agent.py` | `build_graph()` |
| State schema | `src/state.py` | `AgentState` |
| Source fan-out | `src/tools/parallel_tools.py` | `parallel_search_node()` |
| Source fetchers | `src/tools/research_tools.py` | `search_*_node()` |
| RAG retrieval | `src/tools/rag_tools.py` | `local_rag_node()` |
| LLM synthesis | `src/tools/synthesis_tools.py` | `consolidate_research_node()` |
| Report rendering | `src/tools/reporting_tools.py` | `generate_report_node()` |
| Re-plan routing | `src/tools/router_tools.py` | `evaluate_research_node()`, `route_evaluation()` |
| Session persistence | `src/db_manager.py` | `save_session()`, `load_session()` |
| Configuration | `src/config.py` | `Settings` (Pydantic) |
