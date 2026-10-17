#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for Research-Agent.

Exposes the LangGraph research agent as MCP tools via JSON-RPC over stdio.
Any MCP-compatible client (Claude Desktop, Continue, Cline, etc.) can invoke:

  - research              Run a research job and wait for the result (blocking).
  - start_research        Start a research job in the background; returns a job_id.
  - get_research_result   Poll a background job; returns the report when done.

Long runs (deep research on a local LLM can take several minutes) should use
start_research + get_research_result so the client never hits a request timeout.

Reports can optionally be copied into a directory of the client's choosing
(e.g. an Obsidian vault) via ``output_dir``. For safety, ``output_dir`` must be
inside the root configured in the ``RESEARCH_AGENT_OUTPUT_ROOT`` environment
variable; if that variable is unset, ``output_dir`` is rejected.

Protocol: JSON-RPC 2.0 over stdin/stdout
Spec:    https://spec.modelcontextprotocol.io/

Usage:
    python mcp_server.py           # stdio transport (for MCP clients)
    python mcp_server.py --test    # interactive test mode
"""

import sys
import json
import subprocess
import os
import time
import re
import argparse
import threading
import uuid
from datetime import date
from pathlib import Path
from typing import Any

# ── Project root (where this script lives) ────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
_VENV_CANDIDATE = PROJECT_ROOT / "venv" / "bin" / "python"
VENV_PYTHON = _VENV_CANDIDATE if _VENV_CANDIDATE.exists() else Path(sys.executable)

# Load .env so subprocesses inherit API keys (TAVILY, YOUTUBE, etc.)
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=False)
    except ImportError:
        pass
MAIN_SCRIPT = PROJECT_ROOT / "src" / "main.py"
REPORTS_DIR = PROJECT_ROOT / "reports"

# ── MCP protocol constants ─────────────────────────────────────────────────
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "research-agent"
SERVER_VERSION = "1.1.0"

RESEARCH_TIMEOUT_SECONDS = int(os.environ.get("RESEARCH_AGENT_TIMEOUT", "900"))
DEPTHS = ["quick", "standard", "deep"]
PERSONAS = ["general", "business", "tech", "academic", "pm", "news_editor"]
LANGS = ["es", "en"]

# ── Background jobs ────────────────────────────────────────────────────────
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
# The agent writes to a shared reports/ directory and usually a single local LLM,
# so runs are serialized: concurrent jobs queue instead of clobbering each other.
_RUN_LOCK = threading.Lock()


def build_command(topic: str, log_level: str = "INFO", depth: str = "standard",
                  persona: str = "general", lang: str = "es") -> list[str]:
    """Build the CLI command that runs the agent."""
    return [
        str(VENV_PYTHON), "-m", "src.main", topic,
        "--log-level", log_level,
        "--depth", depth,
        "--persona", persona,
        "--lang", lang,
    ]


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_len] or "report"


def resolve_output_dir(output_dir: str) -> Path:
    """Validate that output_dir lies inside RESEARCH_AGENT_OUTPUT_ROOT. Raises ValueError otherwise."""
    root = os.environ.get("RESEARCH_AGENT_OUTPUT_ROOT")
    if not root:
        raise ValueError("output_dir not allowed: RESEARCH_AGENT_OUTPUT_ROOT is not configured")
    root_path = Path(root).expanduser().resolve()
    target = Path(output_dir).expanduser()
    if not target.is_absolute():
        target = root_path / target
    target = target.resolve()
    if target != root_path and root_path not in target.parents:
        raise ValueError(f"output_dir must be inside {root_path}")
    return target


def export_report(report_text: str, topic: str, output_dir: Path, depth: str, persona: str) -> Path:
    """Write the report with YAML frontmatter into output_dir and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = output_dir / f"{today}_{_slugify(topic)}.md"
    safe_title = topic.replace('"', "'")
    frontmatter = (
        "---\n"
        f'title: "{safe_title}"\n'
        f"created: {today}\n"
        'author: "Research Agent"\n'
        "tags: [research, research-agent]\n"
        'source: "research-agent"\n'
        f'depth: "{depth}"\n'
        f'persona: "{persona}"\n'
        "---\n\n"
    )
    path.write_text(frontmatter + report_text, encoding="utf-8")
    return path


def _latest_markdown_since(start: float) -> Path | None:
    """Return the newest Markdown report written to REPORTS_DIR after `start`."""
    if not REPORTS_DIR.exists():
        return None
    candidates = [p for p in REPORTS_DIR.glob("*.md") if p.stat().st_mtime >= start - 1]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def run_research(topic: str, log_level: str = "INFO", depth: str = "standard",
                 persona: str = "general", lang: str = "es", output_dir: str | None = None,
                 include_report: bool = True) -> dict[str, Any]:
    """Run the Research Agent CLI and return structured results."""
    if depth not in DEPTHS:
        return {"error": f"Invalid depth '{depth}'. Use one of {DEPTHS}", "topic": topic}
    if persona not in PERSONAS:
        return {"error": f"Invalid persona '{persona}'. Use one of {PERSONAS}", "topic": topic}
    if lang not in LANGS:
        return {"error": f"Invalid lang '{lang}'. Use one of {LANGS}", "topic": topic}
    export_dir = None
    if output_dir:
        try:
            export_dir = resolve_output_dir(output_dir)
        except ValueError as e:
            return {"error": str(e), "topic": topic}
    if not MAIN_SCRIPT.exists():
        return {"error": f"Main script not found at {MAIN_SCRIPT}"}

    with _RUN_LOCK:
        return _run_locked(topic, log_level, depth, persona, lang, export_dir, include_report)


def _run_locked(topic: str, log_level: str, depth: str, persona: str, lang: str,
                export_dir: Path | None, include_report: bool) -> dict[str, Any]:
    cmd = build_command(topic, log_level, depth, persona, lang)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=RESEARCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": f"Research agent timed out after {RESEARCH_TIMEOUT_SECONDS} seconds",
            "topic": topic,
        }

    elapsed = round(time.time() - start, 1)
    result: dict[str, Any] = {
        "topic": topic,
        "depth": depth,
        "persona": persona,
        "exit_code": proc.returncode,
        "elapsed_seconds": elapsed,
        "output_files": {},
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
        "stderr_tail": "",
    }

    if proc.returncode != 0:
        result["error"] = "Research agent exited with a non-zero status"
        result["stderr_tail"] = proc.stderr[-1000:] if proc.stderr else "(no stderr)"
        return result

    for name, filename in [("html", "reporte_final.html"), ("pdf", "reporte_investigacion.pdf"),
                           ("docx", "reporte_final.docx")]:
        path = REPORTS_DIR / filename
        if path.exists():
            result["output_files"][name] = str(path)

    md_path = _latest_markdown_since(start)
    if md_path is None:
        result["report"] = "No Markdown report generated."
        result["citation_count"] = 0
        return result

    report_text = md_path.read_text(encoding="utf-8")
    result["output_files"]["markdown"] = str(md_path)
    result["citation_count"] = len(re.findall(r"^- ", report_text, re.MULTILINE))
    if include_report:
        result["report"] = report_text
    else:
        result["report_preview"] = report_text[:3000]
    if export_dir is not None:
        result["exported_to"] = str(export_report(report_text, topic, export_dir, depth, persona))
    return result


def start_job(arguments: dict[str, Any]) -> str:
    """Start run_research in a background thread and return its job id."""
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "topic": arguments.get("topic", ""),
                         "started_at": time.time(), "result": None}

    def _worker():
        try:
            res = run_research(**arguments)
            status = "error" if "error" in res else "done"
        except Exception as e:  # noqa: BLE001 - surface any failure to the client
            res, status = {"error": f"Unexpected failure: {e}"}, "error"
        with _JOBS_LOCK:
            _JOBS[job_id].update(status=status, result=res, finished_at=time.time())

    threading.Thread(target=_worker, daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return {"error": f"Unknown job_id: {job_id}"}
        out = {"job_id": job_id, "status": job["status"], "topic": job["topic"]}
        if job["status"] == "running":
            out["elapsed_seconds"] = round(time.time() - job["started_at"], 1)
        else:
            out["result"] = job["result"]
        return out


# ── Tool definitions ───────────────────────────────────────────────────────

_RESEARCH_PROPERTIES = {
    "topic": {"type": "string", "description": "The research topic or question to investigate."},
    "depth": {"type": "string", "enum": DEPTHS,
              "description": "quick (2 results/source), standard (5) or deep (10). Default: standard."},
    "persona": {"type": "string", "enum": PERSONAS,
                "description": "Persona that shapes source selection and analysis. Default: general."},
    "lang": {"type": "string", "enum": LANGS, "description": "Report language. Default: es."},
    "output_dir": {"type": "string",
                   "description": "Optional directory (inside RESEARCH_AGENT_OUTPUT_ROOT) where a copy of "
                                  "the Markdown report with YAML frontmatter is written."},
    "include_report": {"type": "boolean",
                       "description": "Return the full Markdown report (default true) instead of a 3000-char preview."},
    "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
                  "description": "Logging verbosity (default: INFO)."},
}

TOOLS = [
    {
        "name": "research",
        "description": (
            "Run multi-source internet research on a topic and wait for the result. Searches 10 sources "
            "in parallel (Tavily/web, Wikipedia, arXiv, Semantic Scholar, GitHub, Hacker News, Stack Overflow, "
            "Reddit, YouTube, local RAG) and returns a cited Markdown report. Can take several minutes; prefer "
            "start_research + get_research_result for standard/deep runs."
        ),
        "inputSchema": {"type": "object", "properties": _RESEARCH_PROPERTIES, "required": ["topic"]},
    },
    {
        "name": "start_research",
        "description": "Start the same research in the background and return immediately with a job_id.",
        "inputSchema": {"type": "object", "properties": _RESEARCH_PROPERTIES, "required": ["topic"]},
    },
    {
        "name": "get_research_result",
        "description": "Get the status of a background research job; returns the full result when status is done.",
        "inputSchema": {"type": "object",
                        "properties": {"job_id": {"type": "string", "description": "Id returned by start_research."}},
                        "required": ["job_id"]},
    },
]

_ALLOWED_ARGS = set(_RESEARCH_PROPERTIES)


# ── MCP JSON-RPC message handling ──────────────────────────────────────────

def _tool_result(msg_id, payload: dict[str, Any]) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}],
            "isError": "error" in payload,
        },
    }


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle_request(msg: dict) -> dict | None:
    """Handle a single JSON-RPC request. Returns a response dict or None for notifications."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {}) or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "notifications/initialized":
        return None  # Notification — no response

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}

        if tool_name == "get_research_result":
            job_id = arguments.get("job_id", "")
            if not job_id:
                return _error(msg_id, -32602, "Missing required parameter: job_id")
            return _tool_result(msg_id, get_job(job_id))

        if tool_name not in ("research", "start_research"):
            return _error(msg_id, -32601, f"Unknown tool: {tool_name}")

        if not arguments.get("topic"):
            return _error(msg_id, -32602, "Missing required parameter: topic")
        unknown = set(arguments) - _ALLOWED_ARGS
        if unknown:
            return _error(msg_id, -32602, f"Unknown parameter(s): {sorted(unknown)}")

        if tool_name == "start_research":
            job_id = start_job(arguments)
            return _tool_result(msg_id, {"job_id": job_id, "status": "running", "topic": arguments["topic"]})

        return _tool_result(msg_id, run_research(**arguments))

    return _error(msg_id, -32601, f"Method not found: {method}")


def stdio_loop():
    """Run the MCP server on stdio transport."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stdout.write(json.dumps(_error(None, -32700, f"Parse error: {e}")) + "\n")
            sys.stdout.flush()
            continue

        response = handle_request(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


# ── Interactive test mode ──────────────────────────────────────────────────


def test_mode():
    """Interactive test loop for manual debugging."""
    print("Research-Agent MCP Server — Test Mode")
    print(f"  Python:     {VENV_PYTHON}")
    print(f"  Agent:      {MAIN_SCRIPT}")
    print(f"  Reports:    {REPORTS_DIR}")
    print(f"  Export root:{os.environ.get('RESEARCH_AGENT_OUTPUT_ROOT', '(not set)')}")
    print()
    print("Commands: topic <text> | quit")
    print()

    while True:
        try:
            cmd = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue
        if cmd.lower() in ("quit", "exit", "q"):
            break
        if cmd.lower().startswith("topic "):
            topic = cmd[6:].strip()
            print(f"Running research on: {topic}")
            result = run_research(topic, include_report=False)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Unknown command. Use: topic <text> | quit")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research-Agent MCP Server")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in interactive test mode instead of stdio MCP mode",
    )
    args = parser.parse_args()

    if args.test:
        test_mode()
    else:
        stdio_loop()
