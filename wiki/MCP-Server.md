# MCP Server

`mcp_server.py` (version 1.1.0) exposes the research agent to any MCP client (Claude Desktop, Claude Code, Continue, Cline) as JSON-RPC 2.0 over stdio. Each call runs `src/main.py` in a subprocess using the project's `venv/bin/python` (falling back to the interpreter running the server).

## Tools

| Tool | Behaviour |
|------|-----------|
| `research` | Runs a job and blocks until the report is ready. Fine for `quick`; may hit client timeouts on `standard`/`deep`. |
| `start_research` | Starts the same job in a background thread and returns a `job_id` immediately. |
| `get_research_result` | Takes a `job_id`; returns the status, and the report once `status` is `done`. |

For long runs (deep research on a local LLM can take several minutes) use `start_research` + `get_research_result` so the client never hits a request timeout.

## Arguments

| Argument | Values | Default |
|----------|--------|---------|
| `topic` (required) | free text | — |
| `depth` | `quick` (2 results/source), `standard` (5), `deep` (10) | `standard` |
| `persona` | `general`, `business`, `tech`, `academic`, `pm`, `news_editor` | `general` |
| `lang` | `es`, `en` | `es` |
| `include_report` | `true` returns the full Markdown report; `false` a 3000-char preview | `true` |
| `output_dir` | directory for a copy of the report (see below) | none |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

## Exporting to a vault

`output_dir` writes a copy of the report, with YAML frontmatter, into a directory such as an Obsidian vault. It is sandboxed:

- It must be inside the directory set in `RESEARCH_AGENT_OUTPUT_ROOT`.
- If that variable is unset, `output_dir` is **rejected** (no default).

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `RESEARCH_AGENT_OUTPUT_ROOT` | Root allowed for `output_dir` | unset (export disabled) |
| `RESEARCH_AGENT_TIMEOUT` | Seconds before a run is aborted | `900` |

Runs are serialized: one research job at a time. The server loads `.env` from the project root so the subprocess inherits the API keys (Tavily, YouTube, ...).

## Claude Desktop on Windows with the agent in WSL

```json
"research-agent": {
  "command": "wsl.exe",
  "args": ["-e", "bash", "-lc", "cd ~/repos/Research-Agent && RESEARCH_AGENT_OUTPUT_ROOT=/mnt/c/path/to/Vault venv/bin/python mcp_server.py"]
}
```

## Testing

- `python mcp_server.py --test` starts an interactive test mode.
- `tests/test_mcp_server.py` (16 tests) covers the tools, the background jobs and the `output_dir` sandbox.

## Non-obvious facts

- The report is located by modification time in `reports/`, not by a topic-derived filename (which was fragile).
- Earlier versions reported a 180 s timeout while the real limit was 420 s; the limit is now configurable and reported accurately.
