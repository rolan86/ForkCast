import os
from pathlib import Path


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
