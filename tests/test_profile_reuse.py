# tests/test_profile_reuse.py
"""Tests for profile reuse logic in prepare_simulation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.simulation.prepare import find_reusable_profiles


class TestFindReusableProfiles:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_db_path, tmp_data_dir):
        self.db_path = tmp_db_path
        self.data_dir = tmp_data_dir
        init_db(self.db_path)
        # Create project with domain
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', 'social-media', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, created_at) "
                "VALUES ('g1', 'p1', 'complete', datetime('now'))"
            )

    def _create_sim_with_profiles(self, sim_id, graph_id="g1", domain="social-media", profiles=None):
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES (?, 'p1', ?, 'prepared', 'claude', '[\"twitter\"]', datetime('now'))",
                (sim_id, graph_id),
            )
        if profiles is None:
            profiles = [{"agent_id": 0, "name": "Alice", "entity_source": "Alice"}]
        sim_dir = self.data_dir / sim_id / "profiles"
        sim_dir.mkdir(parents=True)
        (sim_dir / "agents.json").write_text(json.dumps(profiles))

    def test_finds_profiles_with_matching_criteria(self):
        self._create_sim_with_profiles("sim_old")
        result = find_reusable_profiles(
            db_path=self.db_path, data_dir=self.data_dir,
            project_id="p1", graph_id="g1", domain="social-media",
        )
        assert result is not None
        assert result["simulation_id"] == "sim_old"
        assert result["count"] == 1

    def test_no_match_different_graph(self):
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, created_at) "
                "VALUES ('g2', 'p1', 'complete', datetime('now'))"
            )
        self._create_sim_with_profiles("sim_old", graph_id="g2")
        result = find_reusable_profiles(
            db_path=self.db_path, data_dir=self.data_dir,
            project_id="p1", graph_id="g1", domain="social-media",
        )
        assert result is None

    def test_no_match_different_domain(self):
        self._create_sim_with_profiles("sim_old")
        result = find_reusable_profiles(
            db_path=self.db_path, data_dir=self.data_dir,
            project_id="p1", graph_id="g1", domain="finance",
        )
        assert result is None

    def test_no_match_null_graph_id(self):
        self._create_sim_with_profiles("sim_old", graph_id=None)
        result = find_reusable_profiles(
            db_path=self.db_path, data_dir=self.data_dir,
            project_id="p1", graph_id="g1", domain="social-media",
        )
        assert result is None

    def test_no_match_when_profiles_file_missing(self):
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES ('sim_no_file', 'p1', 'g1', 'prepared', 'claude', '[\"twitter\"]', datetime('now'))"
            )
        result = find_reusable_profiles(
            db_path=self.db_path, data_dir=self.data_dir,
            project_id="p1", graph_id="g1", domain="social-media",
        )
        assert result is None
