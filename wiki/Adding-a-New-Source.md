# Adding a New Research Source

Sources are plain functions that the `parallel_search` node runs in a thread pool. They are **not** separate nodes of the LangGraph graph (the graph has 9 nodes and none per source). Use `search_scholar_node` in `src/tools/research_tools.py` as the reference implementation.

## 1. Write the source function

Add it to `src/tools/research_tools.py` (or a new file under `src/tools/`):

```python
def search_mysource_node(state: AgentState) -> dict:
    """Search MySource and return structured results."""
    logger.info("mysource_search_started")
    queries = state.get("queries", {})
    query = queries.get("en", state["topic"])
    max_results = get_max_results(state)

    # Results go through a container dict so the main thread can read what
    # was collected even if the worker times out.
    container = {"data": []}

    def run_search():
        try:
            for item in my_api_search(query, limit=max_results):
                container["data"].append({
                    "title": item.title,
                    "content": item.summary,
                    "url": item.url,
                })
        except Exception as e:
            logger.error(f"MySource API error: {e}")

    thread = threading.Thread(target=run_search)
    thread.start()
    thread.join(timeout=25)
    results = [] if thread.is_alive() else container["data"]

    return {
        "mysource_research": results,
        "next_node": update_next_node(state, "mysource"),
        "source_metadata": {"mysource": {"source_type": "web", "reliability": 3}},
    }
```

`reliability` (1–5) is passed to the LLM during synthesis, so pick it honestly.

## 2. Add the state key

In `src/state.py`, `AgentState` is a `TypedDict`:

```python
mysource_research: List[dict]
```

Also add `"mysource_research": state.get("mysource_research", [])` to the dict returned by `initialize_state_node` in `src/agent.py`.

## 3. Register the source

- `src/tools/parallel_tools.py`: import the function and add `"mysource": search_mysource_node` to the `source_functions` dict.
- `src/agent.py`: add `"mysource": "search_mysource"` to the `mapping` in `route_research`.
- `src/tools/router_tools.py`: add a `- mysource: ...` line to the `FUENTES DISPONIBLES` list in the planning prompt, so the planner knows when to pick it.

## 4. Wire up the UI

- `src/app.py`: add a checkbox to the `sources` dict, add the code to `selected_sources` where relevant, and add its display name and progress message.
- `src/i18n.py`: add `node_search_mysource` in both the `es` and `en` blocks.

## 5. Show it in the reports

`src/tools/reporting_tools.py` builds each section from the state keys. Add `mysource_research` next to `scholar_research` (search for `scholar` to find every place: the section titles, the HTML/PDF/DOCX/Markdown builders, and the source list).

## 6. Test it

Create `tests/test_mysource_tools.py` following `tests/test_research_tools.py` (mock the external API), then run:

```bash
venv/bin/python -m pytest tests -q
```

## 7. Open a pull request

See [CONTRIBUTING.md](https://github.com/RobertoDeLaCamara/Research-Agent/blob/main/CONTRIBUTING.md) for the checklist. The `new_source.md` issue template pre-fills the key fields.
