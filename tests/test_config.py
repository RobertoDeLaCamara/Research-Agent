from src.config import Settings


def test_settings_ignore_unknown_env_file_keys(tmp_path, monkeypatch):
    """Keys read elsewhere via os.environ (RAG_MODE, RERANK_URL...) must not break Settings."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)  # a real env var would win over the file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OLLAMA_MODEL=test-model\n"
        "RAG_MODE=hybrid\n"
        "RERANK_URL=http://localhost:8099/rerank\n"
        "LIGHT_LLM_MODEL=tiny\n"
    )

    settings = Settings(_env_file=env_file)

    assert settings.ollama_model == "test-model"
    assert not hasattr(settings, "rag_mode")
