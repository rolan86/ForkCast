"""Tests for panel interaction -- concurrent multi-agent Q&A."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.report.models import StreamEvent


def _setup_panel(db_path, data_dir, sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'prepared', '{}')", (sim_id,),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "Curious researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Test",
         "persona": "Skeptical plumber", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestPanelInteraction:
    def test_streams_responses_from_multiple_agents(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_panel(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.side_effect = lambda **kwargs: iter([
            StreamEvent(type="text_delta", data="Test response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.panel import panel_interview

        events = list(panel_interview(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_ids=[0, 1],
            question="What do you think?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        agent_done_events = [e for e in events if e.type == "agent_done"]
        assert len(agent_done_events) == 2
        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1

    def test_persists_panel_conversation(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_panel(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.side_effect = lambda **kwargs: iter([
            StreamEvent(type="text_delta", data="Answer"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.panel import panel_interview

        events = list(panel_interview(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_ids=[0],
            question="Test?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        # Panel stores a panel-prefixed conversation
        with get_db(tmp_db_path) as conn:
            rows = conn.execute(
                "SELECT conversation_id FROM chat_history WHERE conversation_id LIKE 'panel_%'"
            ).fetchall()
            assert len(rows) > 0
