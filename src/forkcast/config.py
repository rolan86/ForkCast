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

DEFAULT_PREP_MODEL = "claude-haiku-4-5"

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
    llm_provider: str = field(default_factory=lambda: _env("FORKCAST_LLM_PROVIDER", "claude"))
    ollama_base_url: str = field(default_factory=lambda: _env("FORKCAST_OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    ollama_model: str = field(default_factory=lambda: _env("FORKCAST_OLLAMA_MODEL", "llama3.1"))

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


def get_available_models(settings: Settings | None = None) -> list[dict]:
    """Return model list, adding Ollama model when provider is ollama.

    Note: signature accepts Optional settings (defaults to get_settings()) for ergonomics.
    This is an intentional improvement over the spec's required-param signature.
    """
    models = list(AVAILABLE_MODELS)
    if settings is None:
        settings = get_settings()
    if settings.llm_provider == "ollama":
        models.append({
            "id": settings.ollama_model,
            "label": f"{settings.ollama_model} (Ollama)",
            "supports_thinking": False,
        })
    return models
