import os
from pathlib import Path

from forkcast.config import AVAILABLE_MODELS, get_available_models, get_settings, reset_settings


def test_settings_loads_defaults():
    """Settings should have sensible defaults when no env vars are set."""
    from forkcast.config import Settings

    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.port == 5001
    assert s.log_level == "info"
    assert isinstance(s.data_dir, Path)
    assert isinstance(s.domains_dir, Path)


def test_settings_reads_env(monkeypatch):
    """Settings should read from environment variables."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setenv("FORKCAST_PORT", "8080")
    monkeypatch.setenv("FORKCAST_LOG_LEVEL", "debug")

    from forkcast.config import Settings

    s = Settings()
    assert s.anthropic_api_key == "sk-test-key"
    assert s.port == 8080
    assert s.log_level == "debug"


def test_settings_data_dir_resolved(tmp_path, monkeypatch):
    """data_dir should be resolved to an absolute path."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_path / "mydata"))

    from forkcast.config import Settings

    s = Settings()
    assert s.data_dir.is_absolute()


def test_get_settings_returns_singleton():
    """get_settings should return the same instance."""
    from forkcast.config import get_settings

    a = get_settings()
    b = get_settings()
    assert a is b


def test_default_llm_provider(monkeypatch):
    """Default provider is claude."""
    monkeypatch.delenv("FORKCAST_LLM_PROVIDER", raising=False)
    reset_settings()
    s = get_settings()
    assert s.llm_provider == "claude"
    reset_settings()


def test_ollama_provider(monkeypatch):
    """Provider can be set to ollama."""
    monkeypatch.setenv("FORKCAST_LLM_PROVIDER", "ollama")
    reset_settings()
    s = get_settings()
    assert s.llm_provider == "ollama"
    assert s.ollama_base_url == "http://localhost:11434/v1"
    assert s.ollama_model == "llama3.1"
    reset_settings()


def test_get_available_models_claude(monkeypatch):
    """Claude provider returns only AVAILABLE_MODELS."""
    monkeypatch.delenv("FORKCAST_LLM_PROVIDER", raising=False)
    reset_settings()
    s = get_settings()
    models = get_available_models(s)
    assert len(models) == len(AVAILABLE_MODELS)
    assert all(m["id"].startswith("claude-") for m in models)
    reset_settings()


def test_get_available_models_ollama(monkeypatch):
    """Ollama provider appends the configured model."""
    monkeypatch.setenv("FORKCAST_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("FORKCAST_OLLAMA_MODEL", "mistral")
    reset_settings()
    s = get_settings()
    models = get_available_models(s)
    assert len(models) == len(AVAILABLE_MODELS) + 1
    ollama_model = models[-1]
    assert ollama_model["id"] == "mistral"
    assert ollama_model["label"] == "mistral (Ollama)"
    assert ollama_model["supports_thinking"] is False
    reset_settings()
