#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for Research-Agent.

Exposes the LangGraph research agent as an MCP tool via JSON-RPC over stdio.
Any MCP-compatible client (Claude Desktop, Continue, Cline, etc.) can invoke
the `research` tool to run exhaustive 10-source internet research.

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
from pathlib import Path
from typing import Any

# ── Project root (where this script lives) ────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"

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
SERVER_VERSION = "1.0.0"


def run_research(topic: str, log_level: str = "INFO") -> dict[str, Any]:
    """Run the Research Agent CLI and return structured results."""
    if not VENV_PYTHON.exists():
        return {"error": f"Virtualenv Python not found at {VENV_PYTHON}"}
    if not MAIN_SCRIPT.exists():
        return {"error": f"Main script not found at {MAIN_SCRIPT}"}

    cmd = [str(VENV_PYTHON), "-m", "src.main", topic, "--log-level", log_level]
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
            timeout=420,  # 7-minute hard timeout (qwen3:14b on CPU needs ~6 min)
        )
    except subprocess.TimeoutExpired:
        return {"error": "Research agent timed out after 180 seconds", "topic": topic}

    elapsed = round(time.time() - start, 1)

    # Build safe topic for filename matching
    safe_topic = topic.replace(" ", "_").replace("/", "_").replace("\\", "_")[:30]
    md_path = REPORTS_DIR / f"reporte_{safe_topic}.md"
    html_path = REPORTS_DIR / "reporte_final.html"
    pdf_path = REPORTS_DIR / "reporte_investigacion.pdf"
    docx_path = REPORTS_DIR / "reporte_final.docx"

    result: dict[str, Any] = {
        "topic": topic,
        "exit_code": proc.returncode,
        "elapsed_seconds": elapsed,
        "output_files": {},
        "stdout_tail": "",
        "stderr_tail": "",
    }

    if proc.returncode == 0:
        # Gather output files
        for name, path in [
            ("markdown", md_path),
            ("html", html_path),
            ("pdf", pdf_path),
            ("docx", docx_path),
        ]:
            if path.exists():
                result["output_files"][name] = str(path)

        # Read the Markdown report for summary
        if md_path.exists():
            report_text = md_path.read_text(encoding="utf-8")
            result["report_preview"] = report_text[:3000]
            # Extract bibliography count
            bib_count = len(re.findall(r"^- ", report_text, re.MULTILINE))
            result["citation_count"] = bib_count
        else:
            result["report_preview"] = "No Markdown report generated."
            result["citation_count"] = 0

        result["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""
    else:
        result["stderr_tail"] = proc.stderr[-1000:] if proc.stderr else "(no stderr)"
        result["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""

    return result


# ── MCP JSON-RPC message handling ──────────────────────────────────────────


def handle_request(msg: dict) -> dict | None:
    """Handle a single JSON-RPC request. Returns a response dict or None for notifications."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "notifications/initialized":
        return None  # Notification — no response

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "research",
                        "description": (
                            "Run exhaustive multi-source internet research on a topic. "
                            "Searches 10 sources in parallel: Tavily/web, Wikipedia, arXiv, "
                            "Semantic Scholar, GitHub, Hacker News, Stack Overflow, Reddit, "
                            "YouTube, and local RAG. Returns a cited report with executive "
                            "synthesis, source-by-source findings, and bibliography. "
                            "Takes 30-120 seconds."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "topic": {
                                    "type": "string",
                                    "description": "The research topic or question to investigate.",
                                },
                                "log_level": {
                                    "type": "string",
                                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
                                    "description": "Logging verbosity (default: INFO).",
                                },
                            },
                            "required": ["topic"],
                        },
                    }
                ]
            },
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name != "research":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        topic = arguments.get("topic", "")
        if not topic:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32602,
                    "message": "Missing required parameter: topic",
                },
            }

        log_level = arguments.get("log_level", "INFO")
        result = run_research(topic, log_level)

        # Format the response as MCP tool result content
        content_text = json.dumps(result, indent=2, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": content_text,
                    }
                ],
                "isError": "error" in result,
            },
        }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


def stdio_loop():
    """Run the MCP server on stdio transport."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {e}",
                },
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
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
            result = run_research(topic)
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
