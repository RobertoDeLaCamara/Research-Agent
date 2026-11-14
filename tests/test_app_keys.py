"""UI regression tests: what a visitor types in the sidebar stays in their session."""
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.i18n import T

APP = str(Path(__file__).parent.parent / "src" / "app.py")
ES = T["es"]
KEY_NAMES = ("OPENAI_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN", "YOUTUBE_API_KEY")


@pytest.fixture
def clean_server(monkeypatch):
    """A server with no keys of its own, running as a public Space."""
    for name in KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(f"src.config.settings.{name.lower()}", None)
    monkeypatch.setenv("SPACE_ID", "demo/space")
    # app.py loads the project's .env at import; keep a developer's keys out of the test
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)


def _open_app():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    return at


def _text_input(at, label):
    return next(t for t in at.text_input if t.label.startswith(label))


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_llm_key_from_the_panel_stays_in_the_visitors_session(clean_server):
    visitor = _open_app()
    _text_input(visitor, "API Key").input("sk-visitor")
    _button(visitor, ES["hf_key_apply"]).click()
    visitor.run()

    assert not visitor.exception
    assert visitor.session_state["credentials"]["OPENAI_API_KEY"] == "sk-visitor"
    assert "OPENAI_API_KEY" not in os.environ

    # Somebody else opening the app must not inherit that key.
    someone_else = _open_app()
    assert "OPENAI_API_KEY" not in someone_else.session_state["credentials"]
    assert any(ES["hf_key_warning"] in w.value for w in someone_else.warning)


def test_optional_keys_stay_in_the_visitors_session(clean_server):
    visitor = _open_app()
    _text_input(visitor, ES["opt_keys_tavily"]).input("tvly-visitor")
    _button(visitor, ES["opt_keys_apply"]).click()
    visitor.run()

    assert not visitor.exception
    assert visitor.session_state["credentials"]["TAVILY_API_KEY"] == "tvly-visitor"
    assert "TAVILY_API_KEY" not in os.environ

    someone_else = _open_app()
    assert _text_input(someone_else, ES["opt_keys_tavily"]).value == ""


def test_server_key_is_never_sent_to_the_browser(clean_server, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-server-secret")

    at = _open_app()
    field = _text_input(at, ES["opt_keys_tavily"])

    assert field.disabled
    assert field.value == ""
