"""Tests for report post-processor framework."""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forkcast.db.connection import init_db, get_db
from forkcast.db.schema import SCHEMA_VERSION, TABLES_V6, MIGRATION_V6_TO_V7
from forkcast.report.postprocess import postprocess_report


@dataclass
class FakeDomain:
    """Minimal domain-like object for testing."""
    name: str = "test-domain"
    prompts: dict = field(default_factory=dict)


class TestMigrationV6ToV7:
    """DB migration: v6 → v7 adds structured_data_json column."""

    def test_fresh_install_has_structured_data_column(self, tmp_path):
        db_path = tmp_path / "fresh.db"
        init_db(db_path)
        with get_db(db_path) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            assert int(row[0]) == 7
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'ready', 'R', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status) VALUES ('s1', 'p1', 'completed')"
            )
            conn.execute(
                "INSERT INTO reports (id, simulation_id, status, structured_data_json) "
                "VALUES ('r1', 's1', 'completed', ?)",
                (json.dumps({"direction": "bull"}),),
            )
            fetched = conn.execute(
                "SELECT structured_data_json FROM reports WHERE id = 'r1'"
            ).fetchone()
            assert json.loads(fetched[0]) == {"direction": "bull"}

    def test_migration_from_v6_adds_column(self, tmp_path):
        db_path = tmp_path / "migrate.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(TABLES_V6)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '6')"
        )
        conn.execute(
            "INSERT INTO reports (id, simulation_id, status, created_at) "
            "VALUES ('r1', 's1', 'completed', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        init_db(db_path)

        with get_db(db_path) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            assert int(row[0]) == 7
            fetched = conn.execute(
                "SELECT structured_data_json FROM reports WHERE id = 'r1'"
            ).fetchone()
            assert fetched[0] is None


class TestPostprocessReport:
    """Unit tests for postprocess_report()."""

    def test_returns_none_when_domain_has_no_post_process_prompt(self):
        domain = FakeDomain(prompts={"ontology": Path("/fake/ontology.md")})
        client = MagicMock()
        result = postprocess_report("# Report", domain, client)
        assert result is None
        client.complete.assert_not_called()

    def test_returns_parsed_json_on_valid_response(self, tmp_path):
        prompt_file = tmp_path / "post_process.md"
        prompt_file.write_text("Extract JSON from the report.")
        domain = FakeDomain(prompts={"post_process": prompt_file})

        mock_response = MagicMock()
        mock_response.text = '{"direction": "bull", "confidence_pct": 75}'
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("# Bull Report\nPrice going up.", domain, client)
        assert result == {"direction": "bull", "confidence_pct": 75}
        client.complete.assert_called_once()

    def test_strips_markdown_code_fences(self, tmp_path):
        prompt_file = tmp_path / "post_process.md"
        prompt_file.write_text("Extract JSON.")
        domain = FakeDomain(prompts={"post_process": prompt_file})

        mock_response = MagicMock()
        mock_response.text = '```json\n{"direction": "bear"}\n```'
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("# Report", domain, client)
        assert result == {"direction": "bear"}

    def test_returns_none_on_malformed_json(self, tmp_path):
        prompt_file = tmp_path / "post_process.md"
        prompt_file.write_text("Extract JSON.")
        domain = FakeDomain(prompts={"post_process": prompt_file})

        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all"
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("# Report", domain, client)
        assert result is None

    def test_returns_none_on_empty_report(self, tmp_path):
        prompt_file = tmp_path / "post_process.md"
        prompt_file.write_text("Extract JSON.")
        domain = FakeDomain(prompts={"post_process": prompt_file})

        mock_response = MagicMock()
        mock_response.text = '{}'
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("", domain, client)
        assert result == {}

    def test_handles_nested_json_response(self, tmp_path):
        prompt_file = tmp_path / "post_process.md"
        prompt_file.write_text("Extract JSON.")
        domain = FakeDomain(prompts={"post_process": prompt_file})

        mock_response = MagicMock()
        mock_response.text = '{"direction": "neutral", "top_bull_arguments": ["a", "b"]}'
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("# Report", domain, client)
        assert result["direction"] == "neutral"
        assert result["top_bull_arguments"] == ["a", "b"]


try:
    from forkcast.domains.loader import load_domain, DomainConfig
    _yaml_available = True
except (ImportError, ModuleNotFoundError):
    _yaml_available = False

_skip_if_no_yaml = pytest.mark.skipif(
    not _yaml_available,
    reason="yaml not installed; skipping integration tests that require load_domain",
)


@_skip_if_no_yaml
class TestPostprocessIntegration:
    """Integration: post-processor with real domain configs."""

    def test_prediction_markets_domain_has_post_process_prompt(self):
        """Verify the prediction-markets domain resolves post_process prompt."""
        domains_dir = Path(__file__).parent.parent / "domains"
        if not (domains_dir / "prediction-markets").is_dir():
            pytest.skip("prediction-markets domain not available")
        domain = load_domain("prediction-markets", domains_dir)
        assert "post_process" in domain.prompts
        assert domain.prompts["post_process"].exists()

    def test_default_domain_has_no_post_process_prompt(self, tmp_domains_dir):
        """Domains without post_process.md should not have the key."""
        domain = load_domain("_default", tmp_domains_dir)
        assert "post_process" not in domain.prompts

    def test_domain_without_post_process_returns_none(self, tmp_domains_dir):
        """Calling postprocess_report on a domain without post_process prompt returns None."""
        domain = load_domain("_default", tmp_domains_dir)
        client = MagicMock()
        result = postprocess_report("# Some report content", domain, client)
        assert result is None
        client.complete.assert_not_called()

    def test_postprocess_with_real_domain_and_mock_llm(self):
        """End-to-end: load prediction-markets domain, call postprocess with mock LLM."""
        domains_dir = Path(__file__).parent.parent / "domains"
        if not (domains_dir / "prediction-markets").is_dir():
            pytest.skip("prediction-markets domain not available")
        domain = load_domain("prediction-markets", domains_dir)

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "direction": "bull",
            "confidence_pct": 72,
            "price_target": "$105",
            "invalidation_level": "$88",
            "top_bull_arguments": ["Strong earnings"],
            "top_bear_arguments": ["Rate risk"],
            "key_catalysts": ["Earnings report"],
            "consensus_strength": "moderate",
        })
        client = MagicMock()
        client.complete.return_value = mock_response

        result = postprocess_report("# Prediction Report\nBullish consensus.", domain, client)
        assert result is not None
        assert result["direction"] == "bull"
        assert result["confidence_pct"] == 72
        assert "top_bull_arguments" in result
