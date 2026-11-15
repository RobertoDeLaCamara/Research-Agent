from unittest.mock import MagicMock, patch

import pytest

from src.llm import invoke_light
from src.utils import default_use_rag, swap_local_host


@pytest.mark.parametrize("env,expected", [
    ({}, False),
    ({"BOOKS_RAG_URL": "http://x:8765"}, True),
    ({"BOOKS_RAG_URL": "http://x:8765", "USE_RAG_DEFAULT": "false"}, False),
    ({"USE_RAG_DEFAULT": "yes"}, True),
])
def test_default_use_rag(monkeypatch, env, expected):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert default_use_rag() is expected


def test_swap_local_host():
    assert swap_local_host("http://host.docker.internal:1/a") == "http://127.0.0.1:1/a"
    assert swap_local_host("http://127.0.0.1:1/a") == "http://host.docker.internal:1/a"
    assert swap_local_host("http://example.com/a") == "http://example.com/a"


def _llm(result=None, error=None):
    m = MagicMock()
    m.invoke.side_effect = error
    m.invoke.return_value = result
    return m


def test_invoke_light_falls_back_to_heavy_when_light_model_fails(monkeypatch):
    monkeypatch.setenv("LIGHT_LLM_MODEL", "small")
    light, heavy = _llm(error=RuntimeError("light down")), _llm(result="ok")
    with patch("src.llm.get_llm", side_effect=lambda **kw: light if kw["tier"] == "light" else heavy):
        assert invoke_light(["msg"]) == "ok"
    heavy.invoke.assert_called_once_with(["msg"])


def test_invoke_light_does_not_retry_when_light_is_heavy(monkeypatch):
    llm = _llm(error=RuntimeError("down"))
    with patch("src.llm.get_llm", return_value=llm), pytest.raises(RuntimeError):
        invoke_light(["msg"])
    assert llm.invoke.call_count == 1
