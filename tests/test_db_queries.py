"""Tests for shared DB query helpers."""

from forkcast.db.connection import get_db, init_db
from forkcast.db.queries import get_project_domain, get_domain_for_simulation


class TestGetProjectDomain:
    def test_returns_domain_for_existing_project(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('proj_1', 'social-media', 'Test', 'created', 'req', datetime('now'))"
            )
        assert get_project_domain(tmp_db_path, "proj_1") == "social-media"

    def test_returns_default_for_missing_project(self, tmp_db_path):
        init_db(tmp_db_path)
        assert get_project_domain(tmp_db_path, "nonexistent") == "_default"


class TestGetDomainForSimulation:
    def test_returns_domain_via_simulation_join(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('proj_1', 'social-media', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status, created_at) "
                "VALUES ('sim_1', 'proj_1', 'created', datetime('now'))"
            )
        assert get_domain_for_simulation(tmp_db_path, "sim_1") == "social-media"

    def test_returns_default_for_missing_simulation(self, tmp_db_path):
        init_db(tmp_db_path)
        assert get_domain_for_simulation(tmp_db_path, "nonexistent") == "_default"
