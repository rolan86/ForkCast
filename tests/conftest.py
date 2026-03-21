import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Workaround: uv sets macOS hidden flag on .pth files, preventing
# editable installs from being discovered. Ensure src/ is on sys.path.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


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
    for name in ["ontology.md", "report_guidelines.md", "config_gen.md", "agent_system.md"]:
        (prompts / name).write_text(f"# Default {name}\n\nPlaceholder prompt.\n")
    (prompts / "persona.md").write_text(
        "# Default persona\n\n"
        "Create a persona for {{ entity_name }} ({{ entity_type }}).\n"
        "Scenario: {{ requirement }}\n"
    )

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
