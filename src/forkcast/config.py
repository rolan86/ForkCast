"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AVAILABLE_MODELS = [
    {"id": "claude-haiku-4-5", "label": "Haiku 4.5 (fast, cheap)", "supports_thinking": False},
    {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6 (balanced)", "supports_thinking": True},
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    return int(val) if val is not None else default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    data_dir: Path = field(
        default_factory=lambda: Path(_env("FORKCAST_DATA_DIR", str(_PROJECT_ROOT / "data"))).resolve()
    )
    domains_dir: Path = field(
        default_factory=lambda: Path(_env("FORKCAST_DOMAINS_DIR", str(_PROJECT_ROOT / "domains"))).resolve()
    )
    db_name: str = field(default_factory=lambda: _env("FORKCAST_DB_NAME", "forkcast.db"))
    host: str = field(default_factory=lambda: _env("FORKCAST_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("FORKCAST_PORT", 5001))
    log_level: str = field(default_factory=lambda: _env("FORKCAST_LOG_LEVEL", "info"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset singleton (for testing)."""
    global _settings
    _settings = None
