# ForkCast Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational layer — project structure, database, config, domain plugin loader, Claude client wrapper, CLI skeleton, and FastAPI shell — so that `forkcast domain list` and `forkcast project create` work end-to-end.

**Architecture:** Layered monolith. Single FastAPI app with clean internal layers. Domain plugins are file-based directories loaded at startup. SQLite for persistence. Typer CLI connects to the API server.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (stdlib), NetworkX, ChromaDB, Anthropic SDK, Typer, uv

**Spec:** `docs/specs/2026-03-20-forkcast-design.md`

**IMPORTANT — Clean-Room Implementation:** This is an original product. Do NOT reference, copy, or adapt code from any existing codebase. Design everything from first principles.

---

## File Structure

```
forkcast/
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   └── forkcast/
│       ├── __init__.py              # Package version
│       ├── config.py                # Settings loaded from .env
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py              # Typer root app + subcommand groups
│       │   ├── domain_cmd.py        # `forkcast domain list/create`
│       │   ├── project_cmd.py       # `forkcast project create/list/show`
│       │   └── server_cmd.py        # `forkcast server start`
│       ├── db/
│       │   ├── __init__.py
│       │   ├── connection.py        # get_db() context manager, init_db()
│       │   └── schema.py            # CREATE TABLE statements, migrations
│       ├── domains/
│       │   ├── __init__.py
│       │   ├── loader.py            # Load manifest.yaml, resolve prompts with fallback
│       │   └── scaffold.py          # Generate new domain directories
│       ├── llm/
│       │   ├── __init__.py
│       │   └── client.py            # Claude API: tool_use, think, complete + retry + logging
│       └── api/
│           ├── __init__.py
│           ├── app.py               # FastAPI app factory
│           ├── responses.py         # success/error envelope helpers
│           ├── domain_routes.py     # GET/POST /api/domains
│           └── project_routes.py    # POST /api/projects, GET /api/projects/{id}
├── domains/
│   └── _default/
│       ├── manifest.yaml
│       ├── prompts/
│       │   ├── ontology.md
│       │   ├── persona.md
│       │   ├── report_guidelines.md
│       │   └── config_gen.md
│       └── ontology/
│           └── hints.yaml
└── tests/
    ├── conftest.py                  # Shared fixtures: tmp db, tmp domains dir, mock claude
    ├── test_config.py
    ├── test_db_schema.py
    ├── test_domain_loader.py
    ├── test_domain_scaffold.py
    ├── test_llm_client.py
    ├── test_cli_domain.py
    ├── test_cli_project.py
    ├── test_api_health.py
    ├── test_api_domains.py
    └── test_api_projects.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/forkcast/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml with uv**

```toml
[project]
name = "forkcast"
version = "0.1.0"
description = "Collective intelligence simulation platform"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "anthropic>=0.42",
    "typer[all]>=0.15",
    "networkx>=3.4",
    "chromadb>=0.6",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "python-multipart>=0.0.18",
    "jinja2>=3.1",
    "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.28",
]

[project.scripts]
forkcast = "forkcast.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/forkcast"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .env.example**

```
# Required: Claude API key
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Override defaults
FORKCAST_DATA_DIR=./data
FORKCAST_DOMAINS_DIR=./domains
FORKCAST_DB_NAME=forkcast.db
FORKCAST_HOST=127.0.0.1
FORKCAST_PORT=5001
FORKCAST_LOG_LEVEL=info
```

- [ ] **Step 3: Create src/forkcast/__init__.py**

```python
"""ForkCast — Collective intelligence simulation platform."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create tests/conftest.py with shared fixtures**

```python
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_db_path(tmp_data_dir):
    """Temporary SQLite database path."""
    return tmp_data_dir / "forkcast.db"


@pytest.fixture
def tmp_domains_dir(tmp_path):
    """Temporary domains directory with a _default domain."""
    domains = tmp_path / "domains"
    domains.mkdir()
    default = domains / "_default"
    default.mkdir()
    prompts = default / "prompts"
    prompts.mkdir()

    # Minimal manifest
    (default / "manifest.yaml").write_text(
        "name: _default\n"
        "version: '1.0'\n"
        "description: Default domain\n"
        "language: en\n"
        "sim_engine: claude\n"
        "platforms: [twitter, reddit]\n"
    )

    # Minimal prompt files
    for name in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
        (prompts / name).write_text(f"# Default {name}\n\nPlaceholder prompt.\n")

    # Ontology hints
    ontology = default / "ontology"
    ontology.mkdir()
    (ontology / "hints.yaml").write_text(
        "max_entity_types: 10\n"
        "required_fallbacks:\n"
        "  - Person\n"
        "  - Organization\n"
    )

    return domains


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client for tests that don't need real API calls."""
    mock = MagicMock()
    mock.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="mock response")],
        usage=MagicMock(input_tokens=10, output_tokens=20),
    )
    return mock
```

- [ ] **Step 5: Update .gitignore for Python project**

Add these entries to the existing `.gitignore`:

```
# Python virtualenv
.venv/

# Test / coverage
.pytest_cache/
htmlcov/
.coverage

# uv lock
uv.lock
```

- [ ] **Step 6: Install dependencies with uv**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv sync --dev`
Expected: Dependencies installed, .venv created

- [ ] **Step 7: Verify pytest runs (no tests yet, should collect 0)**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest --co`
Expected: `no tests ran` or empty collection, no import errors

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/ tests/conftest.py
git commit -m "feat: project scaffolding with uv, dependencies, and test fixtures"
```

---

### Task 2: Configuration

**Files:**
- Create: `src/forkcast/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement config.py**

```python
# src/forkcast/config.py
"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/config.py tests/test_config.py
git commit -m "feat: configuration from environment variables with defaults"
```

---

### Task 3: SQLite Database Layer

**Files:**
- Create: `src/forkcast/db/__init__.py`
- Create: `src/forkcast/db/connection.py`
- Create: `src/forkcast/db/schema.py`
- Create: `tests/test_db_schema.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db_schema.py
import sqlite3
from pathlib import Path


def test_init_db_creates_tables(tmp_db_path):
    """init_db should create all required tables."""
    from forkcast.db.connection import init_db

    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "meta",
        "projects",
        "project_files",
        "graphs",
        "simulations",
        "simulation_actions",
        "reports",
        "chat_history",
        "token_usage",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_init_db_sets_schema_version(tmp_db_path):
    """init_db should set schema_version in meta table."""
    from forkcast.db.connection import init_db
    from forkcast.db.schema import SCHEMA_VERSION

    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    conn.close()

    assert row is not None
    assert int(row[0]) == SCHEMA_VERSION


def test_init_db_is_idempotent(tmp_db_path):
    """Calling init_db twice should not error or lose data."""
    from forkcast.db.connection import init_db

    init_db(tmp_db_path)
    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "projects" in tables


def test_get_db_context_manager(tmp_db_path):
    """get_db should yield a working connection and auto-commit."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            ("proj_001", "_default", "Test", "created", "Test requirement"),
        )

    # Verify data persisted after context exit
    verify = sqlite3.connect(tmp_db_path)
    row = verify.execute("SELECT name FROM projects WHERE id = 'proj_001'").fetchone()
    verify.close()
    assert row[0] == "Test"


def test_get_db_rolls_back_on_error(tmp_db_path):
    """get_db should rollback on exception."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    try:
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("proj_002", "_default", "Fail", "created", "Test"),
            )
            raise ValueError("Simulated error")
    except ValueError:
        pass

    verify = sqlite3.connect(tmp_db_path)
    row = verify.execute("SELECT id FROM projects WHERE id = 'proj_002'").fetchone()
    verify.close()
    assert row is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db_schema.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement schema.py**

```python
# src/forkcast/db/schema.py
"""Database schema definitions and migrations."""

SCHEMA_VERSION = 1

TABLES_V1 = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    ontology_json TEXT,
    requirement TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    text_content TEXT,
    size INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS graphs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'created',
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    file_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    graph_id TEXT REFERENCES graphs(id),
    status TEXT NOT NULL DEFAULT 'created',
    engine_type TEXT NOT NULL DEFAULT 'oasis',
    platforms TEXT NOT NULL DEFAULT '["twitter","reddit"]',
    config_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS simulation_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    agent_name TEXT,
    action_type TEXT NOT NULL,
    content TEXT,
    platform TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'created',
    outline_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    tool_calls_json TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_graphs_project ON graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_simulations_project ON simulations(project_id);
CREATE INDEX IF NOT EXISTS idx_actions_simulation ON simulation_actions(simulation_id);
CREATE INDEX IF NOT EXISTS idx_actions_round ON simulation_actions(simulation_id, round);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_report ON chat_history(report_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""
```

- [ ] **Step 4: Implement connection.py**

```python
# src/forkcast/db/connection.py
"""SQLite connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from forkcast.db.schema import SCHEMA_VERSION, TABLES_V1


def init_db(db_path: Path) -> None:
    """Initialize database with schema. Safe to call multiple times."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(TABLES_V1)
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a connection, commits on success, rolls back on error."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 5: Create db/__init__.py**

```python
# src/forkcast/db/__init__.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_db_schema.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/forkcast/db/ tests/test_db_schema.py
git commit -m "feat: SQLite database layer with schema, migrations, and connection management"
```

---

### Task 4: Domain Plugin Loader

**Files:**
- Create: `src/forkcast/domains/__init__.py`
- Create: `src/forkcast/domains/loader.py`
- Create: `tests/test_domain_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_domain_loader.py
from pathlib import Path

import pytest


def test_load_domain_reads_manifest(tmp_domains_dir):
    """load_domain should parse manifest.yaml and return a DomainConfig."""
    from forkcast.domains.loader import load_domain

    domain = load_domain("_default", tmp_domains_dir)
    assert domain.name == "_default"
    assert domain.language == "en"
    assert domain.sim_engine == "claude"
    assert "twitter" in domain.platforms


def test_load_domain_resolves_prompt_paths(tmp_domains_dir):
    """Prompt paths should be resolved to absolute file paths."""
    from forkcast.domains.loader import load_domain

    domain = load_domain("_default", tmp_domains_dir)
    assert domain.prompts["ontology"].exists()
    assert domain.prompts["ontology"].name == "ontology.md"


def test_load_domain_not_found(tmp_domains_dir):
    """load_domain should raise if domain directory doesn't exist."""
    from forkcast.domains.loader import DomainNotFoundError, load_domain

    with pytest.raises(DomainNotFoundError):
        load_domain("nonexistent", tmp_domains_dir)


def test_load_domain_falls_back_to_default(tmp_domains_dir):
    """If a domain is missing a prompt file, fall back to _default."""
    from forkcast.domains.loader import load_domain

    # Create a minimal custom domain with no prompts
    custom = tmp_domains_dir / "custom"
    custom.mkdir()
    (custom / "manifest.yaml").write_text(
        "name: custom\n"
        "version: '1.0'\n"
        "description: Custom domain\n"
        "language: fr\n"
        "sim_engine: oasis\n"
        "platforms: [reddit]\n"
    )

    domain = load_domain("custom", tmp_domains_dir)
    assert domain.name == "custom"
    assert domain.language == "fr"
    # Prompts should fall back to _default
    assert domain.prompts["ontology"].exists()
    assert "_default" in str(domain.prompts["ontology"])


def test_list_domains(tmp_domains_dir):
    """list_domains should return all domains in the directory."""
    from forkcast.domains.loader import list_domains

    domains = list_domains(tmp_domains_dir)
    assert len(domains) >= 1
    names = [d.name for d in domains]
    assert "_default" in names


def test_read_prompt_returns_content(tmp_domains_dir):
    """read_prompt should return the file content as a string."""
    from forkcast.domains.loader import load_domain, read_prompt

    domain = load_domain("_default", tmp_domains_dir)
    content = read_prompt(domain, "ontology")
    assert "Default ontology.md" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_domain_loader.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement loader.py**

```python
# src/forkcast/domains/loader.py
"""Domain plugin loader — reads manifest.yaml, resolves prompts with _default fallback."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class DomainNotFoundError(Exception):
    """Raised when a domain directory does not exist."""


PROMPT_KEYS = ["ontology", "persona", "report_guidelines", "config_generation"]
DEFAULT_PROMPT_FILES = {
    "ontology": "prompts/ontology.md",
    "persona": "prompts/persona.md",
    "report_guidelines": "prompts/report_guidelines.md",
    "config_generation": "prompts/config_gen.md",
}


@dataclass
class DomainConfig:
    """Loaded domain configuration."""

    name: str
    version: str
    description: str
    language: str
    sim_engine: str
    platforms: list[str]
    prompts: dict[str, Path] = field(default_factory=dict)
    ontology_hints_path: Path | None = None
    platform_defaults_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        """The domain's root directory (derived from prompt paths)."""
        for p in self.prompts.values():
            return p.parent.parent
        return Path()


def load_domain(name: str, domains_dir: Path) -> DomainConfig:
    """Load a domain by name from the domains directory.

    Resolves prompt file paths with file-level fallback to _default.
    """
    domain_path = domains_dir / name
    if not domain_path.is_dir():
        raise DomainNotFoundError(f"Domain '{name}' not found at {domain_path}")

    manifest_path = domain_path / "manifest.yaml"
    if not manifest_path.exists():
        raise DomainNotFoundError(f"No manifest.yaml in domain '{name}'")

    with open(manifest_path) as f:
        raw = yaml.safe_load(f)

    default_path = domains_dir / "_default"

    # Resolve prompt files with fallback
    prompt_mapping = raw.get("prompts", {})
    prompts: dict[str, Path] = {}
    for key, default_file in DEFAULT_PROMPT_FILES.items():
        # Check domain-specific path first
        if key in prompt_mapping:
            candidate = domain_path / prompt_mapping[key]
        else:
            candidate = domain_path / default_file

        if candidate.exists():
            prompts[key] = candidate.resolve()
        else:
            # Fall back to _default
            fallback = default_path / default_file
            if fallback.exists():
                prompts[key] = fallback.resolve()

    # Ontology hints
    ontology_cfg = raw.get("ontology", {})
    hints_rel = ontology_cfg.get("hints", "ontology/hints.yaml")
    hints_path = domain_path / hints_rel
    if not hints_path.exists():
        hints_path = default_path / "ontology" / "hints.yaml"
    ontology_hints = hints_path.resolve() if hints_path.exists() else None

    # Platform defaults
    platform_defaults = domain_path / "simulation" / "platform_defaults.yaml"
    if not platform_defaults.exists():
        platform_defaults = default_path / "simulation" / "platform_defaults.yaml"
    platform_defaults_resolved = (
        platform_defaults.resolve() if platform_defaults.exists() else None
    )

    return DomainConfig(
        name=raw.get("name", name),
        version=raw.get("version", "0.0"),
        description=raw.get("description", ""),
        language=raw.get("language", "en"),
        sim_engine=raw.get("sim_engine", "claude"),
        platforms=raw.get("platforms", ["twitter", "reddit"]),
        prompts=prompts,
        ontology_hints_path=ontology_hints,
        platform_defaults_path=platform_defaults_resolved,
        raw=raw,
    )


def list_domains(domains_dir: Path) -> list[DomainConfig]:
    """List all available domains (directories with manifest.yaml)."""
    domains = []
    if not domains_dir.is_dir():
        return domains
    for child in sorted(domains_dir.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").exists():
            try:
                domains.append(load_domain(child.name, domains_dir))
            except DomainNotFoundError:
                continue
    return domains


def read_prompt(domain: DomainConfig, prompt_key: str) -> str:
    """Read prompt content from a domain's resolved prompt file."""
    path = domain.prompts.get(prompt_key)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Prompt '{prompt_key}' not found for domain '{domain.name}'")
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Create domains/__init__.py**

```python
# src/forkcast/domains/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_domain_loader.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/domains/ tests/test_domain_loader.py
git commit -m "feat: domain plugin loader with manifest parsing and fallback resolution"
```

---

### Task 5: Domain Scaffolding

**Files:**
- Create: `src/forkcast/domains/scaffold.py`
- Create: `tests/test_domain_scaffold.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_domain_scaffold.py
from pathlib import Path


def test_scaffold_domain_creates_directory_structure(tmp_domains_dir):
    """scaffold_domain should create the full domain directory."""
    from forkcast.domains.scaffold import scaffold_domain

    result = scaffold_domain(
        name="my-domain",
        description="Test domain for unit testing",
        language="en",
        sim_engine="oasis",
        platforms=["twitter", "reddit"],
        domains_dir=tmp_domains_dir,
    )

    assert result.is_dir()
    assert (result / "manifest.yaml").exists()
    assert (result / "prompts" / "ontology.md").exists()
    assert (result / "prompts" / "persona.md").exists()
    assert (result / "prompts" / "report_guidelines.md").exists()
    assert (result / "prompts" / "config_gen.md").exists()
    assert (result / "ontology" / "hints.yaml").exists()


def test_scaffold_domain_manifest_content(tmp_domains_dir):
    """scaffold_domain manifest should match the input params."""
    import yaml

    from forkcast.domains.scaffold import scaffold_domain

    result = scaffold_domain(
        name="ad-testing",
        description="Ad copy A/B testing",
        language="en",
        sim_engine="claude",
        platforms=["reddit"],
        domains_dir=tmp_domains_dir,
    )

    with open(result / "manifest.yaml") as f:
        manifest = yaml.safe_load(f)

    assert manifest["name"] == "ad-testing"
    assert manifest["description"] == "Ad copy A/B testing"
    assert manifest["sim_engine"] == "claude"
    assert manifest["platforms"] == ["reddit"]


def test_scaffold_domain_refuses_duplicate(tmp_domains_dir):
    """scaffold_domain should refuse to overwrite an existing domain."""
    import pytest

    from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

    scaffold_domain(
        name="unique-domain",
        description="First",
        language="en",
        sim_engine="oasis",
        platforms=["twitter"],
        domains_dir=tmp_domains_dir,
    )

    with pytest.raises(DomainExistsError):
        scaffold_domain(
            name="unique-domain",
            description="Duplicate",
            language="en",
            sim_engine="oasis",
            platforms=["twitter"],
            domains_dir=tmp_domains_dir,
        )


def test_scaffolded_domain_is_loadable(tmp_domains_dir):
    """A scaffolded domain should be loadable by the domain loader."""
    from forkcast.domains.loader import load_domain
    from forkcast.domains.scaffold import scaffold_domain

    scaffold_domain(
        name="loadable",
        description="Should load",
        language="es",
        sim_engine="claude",
        platforms=["twitter", "reddit"],
        domains_dir=tmp_domains_dir,
    )

    domain = load_domain("loadable", tmp_domains_dir)
    assert domain.name == "loadable"
    assert domain.language == "es"
    assert len(domain.prompts) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_domain_scaffold.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scaffold.py**

```python
# src/forkcast/domains/scaffold.py
"""Generate new domain plugin directories from parameters."""

from pathlib import Path

import yaml


class DomainExistsError(Exception):
    """Raised when attempting to create a domain that already exists."""


_PROMPT_TEMPLATES = {
    "ontology.md": (
        "# Ontology Generation\n\n"
        "You are an expert at extracting structured knowledge from text.\n"
        "Given a document and a prediction question, identify the key entity types\n"
        "and relationship types that are relevant to the domain.\n\n"
        "## Instructions\n\n"
        "- Identify entity types that represent real-world actors or concepts\n"
        "- Define relationship types that capture meaningful connections\n"
        "- Ensure entity types can participate in social interactions\n"
    ),
    "persona.md": (
        "# Persona Generation\n\n"
        "Generate a detailed persona for a simulation agent based on the entity\n"
        "extracted from the knowledge graph.\n\n"
        "## Required Fields\n\n"
        "- Bio (200 characters max)\n"
        "- Detailed persona (behavioral patterns, stance, communication style)\n"
        "- Demographics (age, profession, interests)\n"
    ),
    "report_guidelines.md": (
        "# Report Guidelines\n\n"
        "You are analyzing the results of a multi-agent simulation.\n"
        "Generate a comprehensive prediction report based on the emergent behaviors\n"
        "observed during the simulation.\n\n"
        "## Approach\n\n"
        "- Analyze patterns in agent interactions\n"
        "- Identify key narratives and sentiment shifts\n"
        "- Draw conclusions grounded in simulation data\n"
    ),
    "config_gen.md": (
        "# Simulation Configuration\n\n"
        "Generate simulation parameters based on the entities, domain context,\n"
        "and prediction requirements.\n\n"
        "## Parameters to Generate\n\n"
        "- Time configuration (duration, rounds, peak hours)\n"
        "- Event configuration (initial posts, topics)\n"
        "- Agent behavior configuration (activity levels, stances)\n"
        "- Platform configuration (feed algorithm weights)\n"
    ),
}

_HINTS_TEMPLATE = (
    "# Ontology Hints\n"
    "# Domain-specific guidance for entity extraction\n\n"
    "max_entity_types: 10\n"
    "required_fallbacks:\n"
    "  - Person\n"
    "  - Organization\n"
    "\n"
    "# Add domain-specific entity type suggestions below:\n"
    "# suggested_types:\n"
    "#   - name: Analyst\n"
    "#     description: Financial or market analyst\n"
)


def scaffold_domain(
    name: str,
    description: str,
    language: str,
    sim_engine: str,
    platforms: list[str],
    domains_dir: Path,
) -> Path:
    """Create a new domain plugin directory with template files.

    Returns the path to the created domain directory.
    Raises DomainExistsError if the domain already exists.
    """
    domain_path = domains_dir / name
    if domain_path.exists():
        raise DomainExistsError(f"Domain '{name}' already exists at {domain_path}")

    # Create directory structure
    domain_path.mkdir(parents=True)
    (domain_path / "prompts").mkdir()
    (domain_path / "ontology").mkdir()

    # Write manifest
    manifest = {
        "name": name,
        "version": "1.0",
        "description": description,
        "language": language,
        "sim_engine": sim_engine,
        "platforms": platforms,
        "prompts": {
            "ontology": "prompts/ontology.md",
            "persona": "prompts/persona.md",
            "report_guidelines": "prompts/report_guidelines.md",
            "config_generation": "prompts/config_gen.md",
        },
        "ontology": {
            "hints": "ontology/hints.yaml",
            "max_entity_types": 10,
            "required_fallbacks": ["Person", "Organization"],
        },
    }
    with open(domain_path / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    # Write prompt templates
    for filename, content in _PROMPT_TEMPLATES.items():
        (domain_path / "prompts" / filename).write_text(content, encoding="utf-8")

    # Write ontology hints
    (domain_path / "ontology" / "hints.yaml").write_text(_HINTS_TEMPLATE, encoding="utf-8")

    return domain_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_domain_scaffold.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/domains/scaffold.py tests/test_domain_scaffold.py
git commit -m "feat: domain scaffolding — generate new plugin directories from parameters"
```

---

### Task 6: Claude Client Wrapper

**Files:**
- Create: `src/forkcast/llm/__init__.py`
- Create: `src/forkcast/llm/client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_client.py
from unittest.mock import MagicMock, patch


def test_complete_returns_text(mock_anthropic):
    """complete() should return the text content from Claude's response."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.complete(messages=[{"role": "user", "content": "Hello"}])
    assert result.text == "mock response"
    assert result.input_tokens == 10
    assert result.output_tokens == 20


def test_complete_tracks_usage(mock_anthropic):
    """complete() should populate usage fields."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.complete(messages=[{"role": "user", "content": "test"}])
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.model is not None


def test_tool_use_extracts_tool_calls(mock_anthropic):
    """tool_use() should extract tool call blocks from the response."""
    from forkcast.llm.client import ClaudeClient

    # Set up mock to return a tool_use block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "call_123"
    tool_block.name = "extract_entities"
    tool_block.input = {"entities": [{"name": "Alice", "type": "Person"}]}

    mock_anthropic.messages.create.return_value = MagicMock(
        content=[tool_block],
        usage=MagicMock(input_tokens=50, output_tokens=100),
        model="claude-sonnet-4-6",
        stop_reason="tool_use",
    )

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.tool_use(
        messages=[{"role": "user", "content": "Extract entities"}],
        tools=[{"name": "extract_entities", "description": "test", "input_schema": {}}],
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "extract_entities"
    assert result.tool_calls[0]["input"]["entities"][0]["name"] == "Alice"


def test_client_default_model():
    """ClaudeClient should use a sensible default model."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    assert "claude" in client.default_model
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement client.py**

```python
# src/forkcast/llm/client.py
"""Claude API client wrapper with retry, usage tracking, and multiple calling modes."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
MAX_RETRIES = 3
RETRY_DELAY = 1.0


@dataclass
class LLMResponse:
    """Standardized response from any Claude API call."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = ""
    raw: Any = None


class ClaudeClient:
    """Wrapper around the Anthropic SDK with retry, usage tracking, and convenience methods."""

    def __init__(self, api_key: str, default_model: str = DEFAULT_MODEL):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Standard completion — send messages, get text back."""
        return self._call(
            messages=messages,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def tool_use(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Call with tools — Claude can return tool_use blocks."""
        return self._call(
            messages=messages,
            tools=tools,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def think(
        self,
        messages: list[dict[str, str]],
        thinking_budget: int = 10000,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> LLMResponse:
        """Extended thinking — Claude reasons step by step before responding."""
        return self._call(
            messages=messages,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=1.0,  # Required for extended thinking
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )

    def _call(self, **kwargs: Any) -> LLMResponse:
        """Internal method with retry logic."""
        messages = kwargs.pop("messages")
        system = kwargs.pop("system", None)
        tools = kwargs.pop("tools", None)
        thinking = kwargs.pop("thinking", None)

        create_kwargs: dict[str, Any] = {
            "messages": messages,
            "model": kwargs.get("model", self.default_model),
            "max_tokens": kwargs.get("max_tokens", DEFAULT_MAX_TOKENS),
        }

        if system:
            create_kwargs["system"] = system
        if tools:
            create_kwargs["tools"] = tools
        if thinking:
            create_kwargs["thinking"] = thinking
        if "temperature" in kwargs and thinking is None:
            create_kwargs["temperature"] = kwargs["temperature"]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.messages.create(**create_kwargs)
                return self._parse_response(response)
            except anthropic.RateLimitError as e:
                last_error = e
                wait = RETRY_DELAY * (2**attempt)
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    wait = RETRY_DELAY * (2**attempt)
                    logger.warning(f"API error {e.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

        raise last_error  # type: ignore[misc]

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic API response into standardized LLMResponse."""
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            elif block.type == "thinking":
                # Extended thinking block — captured but not included in text
                pass

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=getattr(response, "model", self.default_model),
            stop_reason=getattr(response, "stop_reason", ""),
            raw=response,
        )
```

- [ ] **Step 4: Create llm/__init__.py**

```python
# src/forkcast/llm/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/llm/ tests/test_llm_client.py
git commit -m "feat: Claude API client wrapper with tool_use, think, complete, and retry"
```

---

### Task 7: FastAPI App Shell + Health Endpoint

**Files:**
- Create: `src/forkcast/api/__init__.py`
- Create: `src/forkcast/api/app.py`
- Create: `src/forkcast/api/responses.py`
- Create: `tests/test_api_health.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_health.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    """Create a test FastAPI app."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """GET /health should return ok status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "ForkCast"


@pytest.mark.asyncio
async def test_not_found_returns_json(app):
    """Unknown routes should return JSON error, not HTML."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nonexistent")

    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement responses.py**

```python
# src/forkcast/api/responses.py
"""Standardized API response helpers."""

from typing import Any

from fastapi.responses import JSONResponse


def success(data: Any = None, status_code: int = 200) -> JSONResponse:
    """Return a success response with the standard envelope."""
    return JSONResponse(content={"success": True, "data": data}, status_code=status_code)


def error(message: str, status_code: int = 400) -> JSONResponse:
    """Return an error response with the standard envelope."""
    return JSONResponse(
        content={"success": False, "error": message}, status_code=status_code
    )
```

- [ ] **Step 4: Implement app.py**

```python
# src/forkcast/api/app.py
"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from forkcast import __version__
from forkcast.api.responses import success
from forkcast.config import get_settings
from forkcast.db.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ForkCast",
        description="Collective intelligence simulation platform",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return success({"status": "ok", "service": "ForkCast", "version": __version__})

    # Import and include routers here as they're built
    # from forkcast.api.domain_routes import router as domain_router
    # app.include_router(domain_router)

    return app
```

- [ ] **Step 5: Create api/__init__.py**

```python
# src/forkcast/api/__init__.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/forkcast/api/ tests/test_api_health.py
git commit -m "feat: FastAPI app factory with health endpoint and response envelope"
```

---

### Task 8: Domain API Routes

**Files:**
- Create: `src/forkcast/api/domain_routes.py`
- Create: `tests/test_api_domains.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_domains.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_list_domains(app, tmp_domains_dir):
    """GET /api/domains should return available domains."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/domains")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    domains = body["data"]
    assert isinstance(domains, list)
    assert any(d["name"] == "_default" for d in domains)


@pytest.mark.asyncio
async def test_create_domain(app, tmp_domains_dir):
    """POST /api/domains should scaffold a new domain."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/domains",
            json={
                "name": "test-domain",
                "description": "A test domain",
                "language": "en",
                "sim_engine": "claude",
                "platforms": ["reddit"],
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "test-domain"

    # Verify domain is now loadable
    assert (tmp_domains_dir / "test-domain" / "manifest.yaml").exists()


@pytest.mark.asyncio
async def test_create_duplicate_domain(app, tmp_domains_dir):
    """POST /api/domains with existing name should fail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first
        await client.post(
            "/api/domains",
            json={"name": "dup", "description": "First", "language": "en", "sim_engine": "oasis", "platforms": ["twitter"]},
        )
        # Duplicate
        resp = await client.post(
            "/api/domains",
            json={"name": "dup", "description": "Second", "language": "en", "sim_engine": "oasis", "platforms": ["twitter"]},
        )

    assert resp.status_code == 409
    assert resp.json()["success"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_domains.py -v`
Expected: FAIL

- [ ] **Step 3: Implement domain_routes.py**

```python
# src/forkcast/api/domain_routes.py
"""Domain management API routes."""

from pydantic import BaseModel

from fastapi import APIRouter

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.domains.loader import list_domains
from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

router = APIRouter(prefix="/api/domains", tags=["domains"])


class CreateDomainRequest(BaseModel):
    name: str
    description: str
    language: str = "en"
    sim_engine: str = "claude"
    platforms: list[str] = ["twitter", "reddit"]


@router.get("")
async def get_domains():
    """List all available domain plugins."""
    settings = get_settings()
    domains = list_domains(settings.domains_dir)
    return success(
        [
            {
                "name": d.name,
                "version": d.version,
                "description": d.description,
                "language": d.language,
                "sim_engine": d.sim_engine,
                "platforms": d.platforms,
            }
            for d in domains
        ]
    )


@router.post("", status_code=201)
async def create_domain(req: CreateDomainRequest):
    """Scaffold a new domain plugin directory."""
    settings = get_settings()
    try:
        path = scaffold_domain(
            name=req.name,
            description=req.description,
            language=req.language,
            sim_engine=req.sim_engine,
            platforms=req.platforms,
            domains_dir=settings.domains_dir,
        )
    except DomainExistsError as e:
        return error(str(e), status_code=409)

    return success(
        {
            "name": req.name,
            "description": req.description,
            "language": req.language,
            "sim_engine": req.sim_engine,
            "platforms": req.platforms,
            "path": str(path),
        }
    )
```

- [ ] **Step 4: Register the router in app.py**

Add to `create_app()` in `src/forkcast/api/app.py`:

```python
from forkcast.api.domain_routes import router as domain_router
app.include_router(domain_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_domains.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/api/domain_routes.py src/forkcast/api/app.py tests/test_api_domains.py
git commit -m "feat: domain API routes — list and create domain plugins"
```

---

### Task 9: Project API Routes

**Files:**
- Create: `src/forkcast/api/project_routes.py`
- Create: `tests/test_api_projects.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_projects.py
import io

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_create_project(app):
    """POST /api/projects should create a project with uploaded files."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/projects",
            data={"domain": "_default", "requirement": "What will happen next?"},
            files={"files": ("test.txt", io.BytesIO(b"Some document content"), "text/plain")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"].startswith("proj_")
    assert body["data"]["status"] == "created"
    assert body["data"]["domain"] == "_default"
    assert len(body["data"]["files"]) == 1


@pytest.mark.asyncio
async def test_create_project_missing_requirement(app):
    """POST /api/projects without requirement should fail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/projects",
            data={"domain": "_default"},
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )

    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_get_project(app):
    """GET /api/projects/{id} should return project details."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        create_resp = await client.post(
            "/api/projects",
            data={"domain": "_default", "requirement": "Test question"},
            files={"files": ("doc.txt", io.BytesIO(b"Document text"), "text/plain")},
        )
        project_id = create_resp.json()["data"]["id"]

        # Get
        resp = await client.get(f"/api/projects/{project_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == project_id
    assert body["data"]["requirement"] == "Test question"


@pytest.mark.asyncio
async def test_get_project_not_found(app):
    """GET /api/projects/{id} with invalid ID should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/projects/proj_nonexistent")

    assert resp.status_code == 404
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_list_projects(app):
    """GET /api/projects should list all projects."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create two projects
        for i in range(2):
            await client.post(
                "/api/projects",
                data={"domain": "_default", "requirement": f"Question {i}"},
                files={"files": (f"doc{i}.txt", io.BytesIO(f"Content {i}".encode()), "text/plain")},
            )

        resp = await client.get("/api/projects")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_projects.py -v`
Expected: FAIL

- [ ] **Step 3: Implement project_routes.py**

```python
# src/forkcast/api/project_routes.py
"""Project management API routes."""

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _generate_id() -> str:
    return f"proj_{secrets.token_hex(6)}"


@router.post("", status_code=201)
async def create_project(
    domain: Annotated[str, Form()],
    requirement: Annotated[str, Form()],
    files: list[UploadFile] = File(...),
    name: Annotated[str | None, Form()] = None,
):
    """Create a new project with uploaded files."""
    settings = get_settings()
    project_id = _generate_id()
    project_name = name or f"Project {project_id[-6:]}"
    now = datetime.now(timezone.utc).isoformat()

    # Create project directory
    project_dir = settings.data_dir / project_id
    uploads_dir = project_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Save files
    saved_files = []
    for f in files:
        content = await f.read()
        file_path = uploads_dir / f.filename
        file_path.write_bytes(content)
        saved_files.append(
            {
                "filename": f.filename,
                "path": str(file_path),
                "size": len(content),
            }
        )

    # Insert into database
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, domain, project_name, "created", requirement, now),
        )
        for sf in saved_files:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, sf["filename"], sf["path"], sf["size"], now),
            )

    return success(
        {
            "id": project_id,
            "name": project_name,
            "domain": domain,
            "status": "created",
            "requirement": requirement,
            "files": saved_files,
            "created_at": now,
        }
    )


@router.get("")
async def list_projects():
    """List all projects."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, domain, name, status, requirement, created_at, updated_at "
            "FROM projects ORDER BY created_at DESC"
        ).fetchall()

    return success([dict(row) for row in rows])


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project details by ID."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, domain, name, status, ontology_json, requirement, created_at, updated_at "
            "FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if row is None:
            return error(f"Project not found: {project_id}", status_code=404)

        files = conn.execute(
            "SELECT filename, path, size FROM project_files WHERE project_id = ?",
            (project_id,),
        ).fetchall()

    project = dict(row)
    project["files"] = [dict(f) for f in files]
    return success(project)
```

- [ ] **Step 4: Register the router in app.py**

Add to `create_app()` in `src/forkcast/api/app.py`:

```python
from forkcast.api.project_routes import router as project_router
app.include_router(project_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_projects.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/api/project_routes.py src/forkcast/api/app.py tests/test_api_projects.py
git commit -m "feat: project API routes — create, list, and get projects with file upload"
```

---

### Task 10: CLI — Domain Commands

**Files:**
- Create: `src/forkcast/cli/__init__.py`
- Create: `src/forkcast/cli/main.py`
- Create: `src/forkcast/cli/domain_cmd.py`
- Create: `tests/test_cli_domain.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_domain.py
from typer.testing import CliRunner


runner = CliRunner()


def test_domain_list(tmp_domains_dir, monkeypatch):
    """forkcast domain list should show available domains."""
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(app, ["domain", "list"])
    assert result.exit_code == 0
    assert "_default" in result.stdout


def test_domain_create(tmp_domains_dir, monkeypatch):
    """forkcast domain create should scaffold a new domain."""
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(
        app,
        [
            "domain",
            "create",
            "--name", "test-cli",
            "--description", "CLI test domain",
            "--language", "en",
            "--engine", "oasis",
            "--platform", "twitter",
            "--platform", "reddit",
        ],
    )
    assert result.exit_code == 0
    assert "test-cli" in result.stdout
    assert (tmp_domains_dir / "test-cli" / "manifest.yaml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_domain.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CLI files**

```python
# src/forkcast/cli/__init__.py
```

```python
# src/forkcast/cli/main.py
"""ForkCast CLI — main entry point."""

import typer

from forkcast.cli.domain_cmd import domain_app

app = typer.Typer(
    name="forkcast",
    help="ForkCast — Collective intelligence simulation platform",
    no_args_is_help=True,
)

app.add_typer(domain_app, name="domain")
```

```python
# src/forkcast/cli/domain_cmd.py
"""CLI commands for domain management."""

from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.domains.loader import list_domains
from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

domain_app = typer.Typer(help="Manage domain plugins", no_args_is_help=True)


@domain_app.command("list")
def domain_list():
    """List available domain plugins."""
    settings = get_settings()
    domains = list_domains(settings.domains_dir)

    if not domains:
        typer.echo("No domains found.")
        return

    typer.echo(f"{'Name':<25} {'Language':<10} {'Engine':<10} {'Description'}")
    typer.echo("-" * 80)
    for d in domains:
        typer.echo(f"{d.name:<25} {d.language:<10} {d.sim_engine:<10} {d.description}")


@domain_app.command("create")
def domain_create(
    name: Annotated[str, typer.Option(help="Domain name (directory name)")],
    description: Annotated[str, typer.Option(help="Short description")],
    language: Annotated[str, typer.Option(help="Default language code")] = "en",
    engine: Annotated[str, typer.Option(help="Simulation engine: oasis or claude")] = "claude",
    platform: Annotated[list[str], typer.Option(help="Simulation platform(s)")] = ["twitter", "reddit"],
):
    """Create a new domain plugin with template files."""
    settings = get_settings()
    try:
        path = scaffold_domain(
            name=name,
            description=description,
            language=language,
            sim_engine=engine,
            platforms=platform,
            domains_dir=settings.domains_dir,
        )
        typer.echo(f"Domain '{name}' created at {path}")
    except DomainExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_domain.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/cli/ tests/test_cli_domain.py
git commit -m "feat: CLI domain commands — list and create domain plugins"
```

---

### Task 11: CLI — Project Commands + Server Start

**Files:**
- Create: `src/forkcast/cli/project_cmd.py`
- Create: `src/forkcast/cli/server_cmd.py`
- Create: `tests/test_cli_project.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_project.py
from typer.testing import CliRunner

runner = CliRunner()


def test_project_list_empty(tmp_data_dir, tmp_domains_dir, monkeypatch):
    """forkcast project list should work with no projects."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    from forkcast.cli.main import app

    result = runner.invoke(app, ["project", "list"])
    assert result.exit_code == 0


def test_project_create(tmp_data_dir, tmp_domains_dir, tmp_path, monkeypatch):
    """forkcast project create should create a project from files."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    # Create a test file to upload
    test_file = tmp_path / "doc.txt"
    test_file.write_text("Some document content for testing.")

    from forkcast.cli.main import app

    result = runner.invoke(
        app,
        ["project", "create", str(test_file), "--domain", "_default", "--prompt", "What will happen?"],
    )
    assert result.exit_code == 0
    assert "proj_" in result.stdout


def test_server_start_help(monkeypatch):
    """forkcast server start --help should show options."""
    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(app, ["server", "start", "--help"])
    assert result.exit_code == 0
    assert "host" in result.stdout.lower() or "port" in result.stdout.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_project.py -v`
Expected: FAIL

- [ ] **Step 3: Implement project_cmd.py and server_cmd.py**

```python
# src/forkcast/cli/project_cmd.py
"""CLI commands for project management."""

import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db

project_app = typer.Typer(help="Manage projects", no_args_is_help=True)


@project_app.command("create")
def project_create(
    files: Annotated[list[Path], typer.Argument(help="Files to upload (PDF, MD, TXT)")],
    domain: Annotated[str, typer.Option(help="Domain plugin name")] = "_default",
    prompt: Annotated[str, typer.Option(help="Prediction requirement / question")] = "",
    name: Annotated[str | None, typer.Option(help="Project name")] = None,
):
    """Create a new project from uploaded files."""
    if not prompt:
        typer.echo("Error: --prompt is required", err=True)
        raise typer.Exit(code=1)

    for f in files:
        if not f.exists():
            typer.echo(f"Error: File not found: {f}", err=True)
            raise typer.Exit(code=1)

    settings = get_settings()
    project_id = f"proj_{secrets.token_hex(6)}"
    project_name = name or f"Project {project_id[-6:]}"
    now = datetime.now(timezone.utc).isoformat()

    # Create project directory and copy files
    project_dir = settings.data_dir / project_id / "uploads"
    project_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        dest = project_dir / f.name
        shutil.copy2(f, dest)
        saved_files.append({"filename": f.name, "path": str(dest), "size": f.stat().st_size})

    # Insert into database
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, domain, project_name, "created", prompt, now),
        )
        for sf in saved_files:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, sf["filename"], sf["path"], sf["size"], now),
            )

    typer.echo(f"Project created: {project_id}")
    typer.echo(f"  Name:   {project_name}")
    typer.echo(f"  Domain: {domain}")
    typer.echo(f"  Files:  {len(saved_files)}")


@project_app.command("list")
def project_list():
    """List all projects."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, domain, name, status, requirement, created_at "
            "FROM projects ORDER BY created_at DESC"
        ).fetchall()

    if not rows:
        typer.echo("No projects found.")
        return

    typer.echo(f"{'ID':<20} {'Domain':<20} {'Status':<12} {'Name'}")
    typer.echo("-" * 80)
    for row in rows:
        typer.echo(f"{row['id']:<20} {row['domain']:<20} {row['status']:<12} {row['name']}")


@project_app.command("show")
def project_show(project_id: str):
    """Show project details."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            typer.echo(f"Project not found: {project_id}", err=True)
            raise typer.Exit(code=1)

        files = conn.execute(
            "SELECT filename, size FROM project_files WHERE project_id = ?",
            (project_id,),
        ).fetchall()

    typer.echo(f"ID:          {row['id']}")
    typer.echo(f"Name:        {row['name']}")
    typer.echo(f"Domain:      {row['domain']}")
    typer.echo(f"Status:      {row['status']}")
    typer.echo(f"Requirement: {row['requirement']}")
    typer.echo(f"Created:     {row['created_at']}")
    if files:
        typer.echo(f"\nFiles ({len(files)}):")
        for f in files:
            typer.echo(f"  - {f['filename']} ({f['size']} bytes)")
```

```python
# src/forkcast/cli/server_cmd.py
"""CLI command to start the ForkCast API server."""

from typing import Annotated

import typer

server_app = typer.Typer(help="Server management")


@server_app.command("start")
def server_start(
    host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 5001,
    reload: Annotated[bool, typer.Option(help="Enable auto-reload")] = False,
):
    """Start the ForkCast API server."""
    import uvicorn

    typer.echo(f"Starting ForkCast server on {host}:{port}")
    uvicorn.run(
        "forkcast.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
```

- [ ] **Step 4: Register in main.py**

Update `src/forkcast/cli/main.py`:

```python
"""ForkCast CLI — main entry point."""

import typer

from forkcast.cli.domain_cmd import domain_app
from forkcast.cli.project_cmd import project_app
from forkcast.cli.server_cmd import server_app

app = typer.Typer(
    name="forkcast",
    help="ForkCast — Collective intelligence simulation platform",
    no_args_is_help=True,
)

app.add_typer(domain_app, name="domain")
app.add_typer(project_app, name="project")
app.add_typer(server_app, name="server")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_project.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/cli/ tests/test_cli_project.py
git commit -m "feat: CLI project and server commands — list, show, and server start"
```

---

### Task 12: Default Domain Plugin + End-to-End Validation

**Files:**
- Create: `domains/_default/manifest.yaml`
- Create: `domains/_default/prompts/ontology.md`
- Create: `domains/_default/prompts/persona.md`
- Create: `domains/_default/prompts/report_guidelines.md`
- Create: `domains/_default/prompts/config_gen.md`
- Create: `domains/_default/ontology/hints.yaml`

- [ ] **Step 1: Create the _default domain directory structure**

```bash
mkdir -p domains/_default/prompts domains/_default/ontology
```

- [ ] **Step 2: Write domains/_default/manifest.yaml**

```yaml
name: _default
version: "1.0"
description: "Default domain — general-purpose collective intelligence simulation"
language: en
sim_engine: claude
platforms:
  - twitter
  - reddit
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks:
    - Person
    - Organization
```

- [ ] **Step 3: Write prompt template files**

Write each file with original, general-purpose prompt content. These are templates — they'll be customized per domain.

`domains/_default/prompts/ontology.md`:
```markdown
# Ontology Generation

You are an expert at extracting structured knowledge from documents.

Given a document and a prediction question, identify the key entity types and relationship types relevant to understanding the scenario.

## Rules

- Identify up to {{ max_entity_types }} entity types
- Entity types should represent real-world actors, organizations, or concepts that could have opinions and participate in discourse
- The last two entity types must always be "Person" and "Organization" as fallbacks
- Define 6-10 relationship types that capture meaningful connections between entities
- Each entity type needs: name, description, and relevant attributes

## Output

Use the extract_entities tool to return your findings.
```

`domains/_default/prompts/persona.md`:
```markdown
# Persona Generation

Generate a detailed simulation persona for the given entity.

## Required Fields

- **bio**: A concise biography (200 characters max)
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - Communication style and tone
  - Key opinions and stances on relevant topics
  - How they interact with others (confrontational, diplomatic, passive)
  - What motivates their participation in discourse
- **age**: Realistic age for this type of entity
- **profession**: Their role or occupation
- **interests**: 3-5 topics they care about

## Context

Entity: {{ entity_name }}
Type: {{ entity_type }}
Description: {{ entity_description }}
Related entities: {{ related_entities }}
```

`domains/_default/prompts/report_guidelines.md`:
```markdown
# Report Generation Guidelines

You are analyzing the results of a multi-agent collective intelligence simulation.

## Your Task

Generate a comprehensive analysis report based on the simulation data. You have access to:
- The knowledge graph (entity relationships and facts)
- Simulation action logs (what agents posted, liked, commented)
- The ability to interview individual agents about their reasoning

## Approach

1. Start by understanding the overall narrative that emerged
2. Identify key turning points, consensus formations, or conflicts
3. Ground your analysis in specific agent actions and quotes
4. Draw conclusions that address the original prediction question

## Style

- Write in clear, analytical prose
- Support claims with evidence from the simulation
- Include direct quotes from agents where relevant
- Structure the report in whatever way best serves the analysis
```

`domains/_default/prompts/config_gen.md`:
```markdown
# Simulation Configuration

Generate simulation parameters for the scenario described below.

## Parameters to Generate

### Time Configuration
- Total simulation hours (12-168)
- Minutes per round (15-60)
- Peak activity hours
- Off-peak activity hours
- Activity multipliers for peak/off-peak

### Event Configuration
- 2-5 initial seed posts to kick off discussion
- 3-7 hot topics that will drive conversation
- Narrative direction (how the conversation should evolve)

### Agent Configuration (per agent)
- Activity level (0.0-1.0)
- Posts per hour
- Comments per hour
- Active hours range
- Sentiment bias (-1.0 to 1.0)
- Stance description
- Influence weight

### Platform Configuration
- Feed algorithm weights (recency, popularity, relevance)
- Viral threshold
- Echo chamber strength

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}
```

- [ ] **Step 4: Write domains/_default/ontology/hints.yaml**

```yaml
# Default ontology extraction hints
max_entity_types: 10
required_fallbacks:
  - Person
  - Organization

# General-purpose suggested types (domain plugins override these)
suggested_types:
  - name: Person
    description: An individual human actor
  - name: Organization
    description: A company, institution, government body, or group
  - name: Community
    description: An informal group with shared interests or identity
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS (across all test files)

- [ ] **Step 6: Verify CLI works end-to-end**

Run: `uv run forkcast domain list`
Expected: Shows `_default` domain with description

Run: `uv run forkcast domain create --name test-e2e --description "End to end test" --language en --engine claude --platform twitter --platform reddit`
Expected: "Domain 'test-e2e' created at domains/test-e2e"

- [ ] **Step 7: Commit**

```bash
git add domains/
git commit -m "feat: default domain plugin with general-purpose prompt templates"
```

- [ ] **Step 8: Final commit — tag Phase 1 complete**

Run all tests one more time:
```bash
uv run pytest -v
```

Then tag:
```bash
git tag v0.1.0-phase1
```

---

## Phase 1 Complete Checklist

At the end of Phase 1, verify:

- [ ] `uv run forkcast domain list` → shows `_default`
- [ ] `uv run forkcast domain create --name X ...` → creates domain directory
- [ ] `uv run forkcast server start` → starts FastAPI on :5001
- [ ] `GET /health` → `{"success": true, "data": {"status": "ok", ...}}`
- [ ] `GET /api/domains` → lists domains
- [ ] `POST /api/domains` → scaffolds new domain
- [ ] `POST /api/projects` → creates project with file upload
- [ ] `GET /api/projects` → lists projects
- [ ] `GET /api/projects/{id}` → returns project details
- [ ] All tests pass: `uv run pytest -v`
- [ ] Clean git history with descriptive commits
