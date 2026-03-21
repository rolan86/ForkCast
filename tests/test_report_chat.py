"""Tests for report chat function."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.report.chat import report_chat
from forkcast.report.models import StreamEvent


def _setup_report(db_path, report_id="r1", sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'completed', '{}')", (sim_id,),
        )
        conn.execute(
            "INSERT INTO reports (id, simulation_id, status, content_markdown) "
            "VALUES (?, ?, 'completed', '# Test Report\n\nContent here.')", (report_id, sim_id),
        )


class TestReportChat:
    def test_streams_text_events(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_report(tmp_db_path)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Hello "),
            StreamEvent(type="text_delta", data="there!"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        events = list(report_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            report_id="r1",
            message="What did the agents discuss?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        text_events = [e for e in events if e.type == "text_delta"]
        assert len(text_events) == 2
        assert text_events[0].data == "Hello "

    def test_persists_messages(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_report(tmp_db_path)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        list(report_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            report_id="r1",
            message="Test question",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        with get_db(tmp_db_path) as conn:
            messages = conn.execute(
                "SELECT * FROM chat_history WHERE conversation_id = 'r1' ORDER BY id"
            ).fetchall()
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"

    def test_report_not_found(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        init_db(tmp_db_path)
        mock_client = MagicMock()

        events = list(report_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            report_id="nonexistent",
            message="Hello",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
