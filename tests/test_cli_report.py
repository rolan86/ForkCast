"""Tests for report CLI commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.main import app
from forkcast.db.connection import get_db, init_db

runner = CliRunner()


class TestReportList:
    def test_list_empty(self, tmp_db_path, monkeypatch):
        init_db(tmp_db_path)
        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "list"])
            assert result.exit_code == 0
            assert "No reports" in result.output or "0" in result.output

    def test_list_with_reports(self, tmp_db_path, monkeypatch):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute("INSERT INTO projects (id, domain, name, status, requirement, created_at) VALUES ('p1','_default','T','ready','R',datetime('now'))")
            conn.execute("INSERT INTO simulations (id, project_id, status) VALUES ('s1','p1','completed')")
            conn.execute("INSERT INTO reports (id, simulation_id, status, content_markdown) VALUES ('r1','s1','completed','# Report')")

        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "list"])
            assert result.exit_code == 0
            assert "r1" in result.output


class TestReportShow:
    def test_show_not_found(self, tmp_db_path):
        init_db(tmp_db_path)
        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "show", "nonexistent"])
            assert result.exit_code == 1

    def test_show_found(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute("INSERT INTO projects (id, domain, name, status, requirement, created_at) VALUES ('p1','_default','T','ready','R',datetime('now'))")
            conn.execute("INSERT INTO simulations (id, project_id, status) VALUES ('s1','p1','completed')")
            conn.execute("INSERT INTO reports (id, simulation_id, status, content_markdown) VALUES ('r1','s1','completed','# Report content')")

        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "show", "r1"])
            assert result.exit_code == 0
            assert "r1" in result.output
            assert "s1" in result.output


class TestReportExport:
    def test_export_not_found(self, tmp_db_path):
        init_db(tmp_db_path)
        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "export", "nonexistent"])
            assert result.exit_code == 1

    def test_export_to_stdout(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute("INSERT INTO projects (id, domain, name, status, requirement, created_at) VALUES ('p1','_default','T','ready','R',datetime('now'))")
            conn.execute("INSERT INTO simulations (id, project_id, status) VALUES ('s1','p1','completed')")
            conn.execute("INSERT INTO reports (id, simulation_id, status, content_markdown) VALUES ('r1','s1','completed','# My Report')")

        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "export", "r1"])
            assert result.exit_code == 0
            assert "# My Report" in result.output

    def test_export_to_file(self, tmp_db_path, tmp_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute("INSERT INTO projects (id, domain, name, status, requirement, created_at) VALUES ('p1','_default','T','ready','R',datetime('now'))")
            conn.execute("INSERT INTO simulations (id, project_id, status) VALUES ('s1','p1','completed')")
            conn.execute("INSERT INTO reports (id, simulation_id, status, content_markdown) VALUES ('r1','s1','completed','# My Report')")

        output_file = str(tmp_path / "report.md")
        with patch("forkcast.cli.report_cmd.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(db_path=tmp_db_path)
            result = runner.invoke(app, ["report", "export", "r1", "-o", output_file])
            assert result.exit_code == 0
            assert "Exported" in result.output
            from pathlib import Path
            assert Path(output_file).read_text() == "# My Report"
