"""Tests for the MCP server (mcp_server.py): tool listing, argument handling,
output_dir sandboxing, report export and background jobs. The agent subprocess
is always mocked, so no LLM or network is needed."""
import json
import subprocess
import time
from types import SimpleNamespace

import pytest

import mcp_server as srv


def _call(name, arguments, msg_id=1):
    resp = srv.handle_request({"jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
                               "params": {"name": name, "arguments": arguments}})
    if "error" in resp:
        return resp
    return json.loads(resp["result"]["content"][0]["text"]), resp["result"]["isError"]


@pytest.fixture
def fake_agent(tmp_path, monkeypatch):
    """Point the server at a temp reports dir and mock the agent subprocess."""
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(srv, "REPORTS_DIR", reports)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        (reports / "reporte_Topic.md").write_text("# Report\n\nBody\n\n## Bib\n- ref 1\n- ref 2\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(srv.subprocess, "run", fake_run)
    return SimpleNamespace(reports=reports, calls=calls)


def test_tools_list_exposes_sync_and_async_tools():
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"research", "start_research", "get_research_result"}
    props = next(t for t in resp["result"]["tools"] if t["name"] == "research")["inputSchema"]["properties"]
    assert {"depth", "persona", "lang", "output_dir", "include_report"} <= set(props)


def test_build_command_passes_depth_persona_lang():
    cmd = srv.build_command("5G core", depth="deep", persona="tech", lang="en")
    assert cmd[cmd.index("--depth") + 1] == "deep"
    assert cmd[cmd.index("--persona") + 1] == "tech"
    assert cmd[cmd.index("--lang") + 1] == "en"


def test_research_returns_full_report_and_citations(fake_agent):
    payload, is_error = _call("research", {"topic": "Topic", "depth": "quick", "persona": "academic"})
    assert not is_error
    assert payload["report"].startswith("# Report")
    assert payload["citation_count"] == 2
    assert payload["depth"] == "quick" and payload["persona"] == "academic"
    assert "--depth" in fake_agent.calls[0] and "quick" in fake_agent.calls[0]


def test_include_report_false_returns_preview(fake_agent):
    payload, _ = _call("research", {"topic": "Topic", "include_report": False})
    assert "report" not in payload
    assert payload["report_preview"].startswith("# Report")


@pytest.mark.parametrize("arg,value", [("depth", "huge"), ("persona", "pirate"), ("lang", "fr")])
def test_invalid_enums_are_rejected(fake_agent, arg, value):
    payload, is_error = _call("research", {"topic": "Topic", arg: value})
    assert is_error and "Invalid" in payload["error"]
    assert fake_agent.calls == []


def test_unknown_parameter_is_rejected():
    resp = _call("research", {"topic": "Topic", "rm_rf": True})
    assert resp["error"]["code"] == -32602


def test_output_dir_requires_configured_root(fake_agent, monkeypatch, tmp_path):
    monkeypatch.delenv("RESEARCH_AGENT_OUTPUT_ROOT", raising=False)
    payload, is_error = _call("research", {"topic": "Topic", "output_dir": str(tmp_path / "vault")})
    assert is_error and "RESEARCH_AGENT_OUTPUT_ROOT" in payload["error"]
    assert fake_agent.calls == []


def test_output_dir_outside_root_is_rejected(fake_agent, monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("RESEARCH_AGENT_OUTPUT_ROOT", str(root))
    payload, is_error = _call("research", {"topic": "Topic", "output_dir": str(tmp_path / "elsewhere")})
    assert is_error and "must be inside" in payload["error"]
    payload, is_error = _call("research", {"topic": "Topic", "output_dir": "../escape"})
    assert is_error


def test_report_is_exported_with_frontmatter(fake_agent, monkeypatch, tmp_path):
    root = tmp_path / "vault"
    monkeypatch.setenv("RESEARCH_AGENT_OUTPUT_ROOT", str(root))
    payload, is_error = _call("research", {"topic": "5G SBA attacks", "depth": "deep", "persona": "tech",
                                           "output_dir": "10_Projects/Research-Agent/reports"})
    assert not is_error
    exported = root / "10_Projects/Research-Agent/reports"
    files = list(exported.glob("*_5g-sba-attacks.md"))
    assert len(files) == 1 and payload["exported_to"] == str(files[0])
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("---\n") and 'depth: "deep"' in text and 'persona: "tech"' in text
    assert "# Report" in text


def test_timeout_message_uses_real_timeout(monkeypatch, fake_agent):
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
    monkeypatch.setattr(srv.subprocess, "run", boom)
    payload, is_error = _call("research", {"topic": "Topic"})
    assert is_error and f"{srv.RESEARCH_TIMEOUT_SECONDS} seconds" in payload["error"]


def test_nonzero_exit_is_reported_as_error(monkeypatch, fake_agent):
    monkeypatch.setattr(srv.subprocess, "run",
                        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="boom"))
    payload, is_error = _call("research", {"topic": "Topic"})
    assert is_error and payload["stderr_tail"] == "boom"


def test_background_job_lifecycle(fake_agent):
    started, _ = _call("start_research", {"topic": "Topic"})
    job_id = started["job_id"]
    assert started["status"] == "running"
    for _ in range(50):
        status, _ = _call("get_research_result", {"job_id": job_id})
        if status["status"] != "running":
            break
        time.sleep(0.05)
    assert status["status"] == "done"
    assert status["result"]["citation_count"] == 2


def test_get_result_unknown_job():
    payload, is_error = _call("get_research_result", {"job_id": "nope"})
    assert is_error and "Unknown job_id" in payload["error"]


def test_initialize_and_notification():
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 7, "method": "initialize"})
    assert resp["result"]["serverInfo"]["version"] == srv.SERVER_VERSION
    assert srv.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
