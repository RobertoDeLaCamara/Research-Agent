"""Per-run credentials: a visitor's keys must never become process-wide."""
import os
import re
import threading
from pathlib import Path

from src.credentials import get_credential, server_has, use_credentials


def test_override_wins_and_is_removed_after_the_run(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "server-key")

    with use_credentials({"TAVILY_API_KEY": "visitor-key"}):
        assert get_credential("TAVILY_API_KEY") == "visitor-key"

    assert get_credential("TAVILY_API_KEY") == "server-key"
    assert os.environ["TAVILY_API_KEY"] == "server-key"  # never written to the environment


def test_empty_override_falls_back_to_server_config(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "server-token")

    with use_credentials({"GITHUB_TOKEN": ""}):
        assert get_credential("GITHUB_TOKEN") == "server-token"


def test_server_has_ignores_visitor_overrides(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("src.config.settings.github_token", None)

    with use_credentials({"GITHUB_TOKEN": "visitor-token"}):
        assert server_has("GITHUB_TOKEN") is False
        assert get_credential("GITHUB_TOKEN") == "visitor-token"


def test_two_concurrent_runs_do_not_see_each_others_keys(monkeypatch):
    """The original bug: session A's key was visible to session B via os.environ."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.config.settings.openai_api_key", None)
    both_inside = threading.Barrier(2, timeout=5)
    seen = {}

    def run(name, creds):
        with use_credentials(creds):
            both_inside.wait()  # both runs are active at the same time
            seen[name] = get_credential("OPENAI_API_KEY")

    a = threading.Thread(target=run, args=("a", {"OPENAI_API_KEY": "key-of-a"}))
    b = threading.Thread(target=run, args=("b", {}))
    a.start()
    b.start()
    a.join(5)
    b.join(5)

    assert seen == {"a": "key-of-a", "b": None}


def test_parallel_search_passes_credentials_to_worker_threads(monkeypatch):
    seen = {}

    def fake_source(state):
        seen["key"] = get_credential("TAVILY_API_KEY")
        seen["thread"] = threading.current_thread().name
        return {}

    monkeypatch.setattr("src.tools.research_tools.search_web_node", fake_source)
    monkeypatch.setattr("src.tools.parallel_tools._write_status", lambda **kwargs: None)
    from src.tools.parallel_tools import parallel_search_node

    with use_credentials({"TAVILY_API_KEY": "visitor-key"}):
        parallel_search_node({"topic": "t", "research_plan": ["web"]})

    assert seen["key"] == "visitor-key"
    assert seen["thread"] != threading.current_thread().name  # it really ran in a pool thread


def test_get_llm_uses_the_runs_backend(monkeypatch):
    for name in ("OPENAI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        monkeypatch.delenv(name, raising=False)
    from src.llm import get_llm

    with use_credentials({
        "OPENAI_API_KEY": "sk-visitor",
        "OLLAMA_BASE_URL": "https://api.groq.com/openai/v1",
        "OLLAMA_MODEL": "llama-3.1-8b-instant",
    }):
        llm = get_llm()

    assert type(llm).__name__ == "ChatOpenAI"
    assert llm.model_name == "llama-3.1-8b-instant"
    assert llm.openai_api_key.get_secret_value() == "sk-visitor"
    assert "OPENAI_API_KEY" not in os.environ


def test_ui_never_writes_to_the_process_environment():
    """Guard: the Streamlit app must keep visitor input in st.session_state."""
    source = (Path(__file__).parent.parent / "src" / "app.py").read_text()

    assert not re.search(r"os\.environ\[[^\]]+\]\s*=", source)
    assert "os.environ.update" not in source and "os.putenv" not in source
