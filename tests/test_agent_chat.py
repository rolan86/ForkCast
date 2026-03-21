"""Tests for agent chat function."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.report.agent_chat import agent_chat
from forkcast.report.models import StreamEvent


def _setup_agent_chat(db_path, data_dir, sim_id="sim1"):
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
            "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
            "VALUES (?, 1, 0, 'alice', 'CREATE_POST', ?, 'twitter', '2026-01-01T00:00:00')",
            (sim_id, json.dumps({"content": "Hello world"})),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [{
        "agent_id": 0, "name": "Alice", "username": "alice",
        "bio": "Test", "persona": "A curious researcher", "age": 30,
        "gender": "female", "profession": "Researcher",
        "interests": ["AI"], "entity_type": "Person", "entity_source": "test",
    }]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestAgentChat:
    def test_streams_in_character(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_agent_chat(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="As a researcher, "),
            StreamEvent(type="text_delta", data="I believe AI should be open."),
            StreamEvent(type="done", data={"input_tokens": 20, "output_tokens": 10, "stop_reason": "end_turn"}),
        ])

        events = list(agent_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id=0,
            message="What do you think about AI?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        text_events = [e for e in events if e.type == "text_delta"]
        assert len(text_events) == 2

    def test_persists_with_synthetic_conversation_id(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_agent_chat(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        list(agent_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id=0,
            message="Hi",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        with get_db(tmp_db_path) as conn:
            messages = conn.execute(
                "SELECT * FROM chat_history WHERE conversation_id = 'agent_chat_sim1_0'"
            ).fetchall()
            assert len(messages) == 2

    def test_agent_not_found(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_agent_chat(tmp_db_path, tmp_data_dir)
        mock_client = MagicMock()

        events = list(agent_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id=999,
            message="Hello",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1

    def test_includes_agent_actions_in_context(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_agent_chat(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Yes"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        list(agent_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id=0,
            message="What did you post?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        call_kwargs = mock_client.stream.call_args[1]
        system = call_kwargs.get("system", "")
        assert "Hello world" in system
