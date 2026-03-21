"""Integration test: simulation → report generation → chat."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.report.agent_chat import agent_chat
from forkcast.report.chat import report_chat
from forkcast.report.models import StreamEvent
from forkcast.report.pipeline import generate_report


def _setup_full_pipeline(db_path, data_dir, sim_id="sim-int-1", project_id="proj-int-1"):
    """Set up a completed simulation for report testing."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Integration Test', 'ready', 'Predict AI trends', datetime('now'))",
            (project_id,),
        )
        config = {
            "total_hours": 1, "minutes_per_round": 30,
            "hot_topics": ["AI"], "seed_posts": [],
            "peak_hours": [], "off_peak_hours": [],
            "peak_multiplier": 1.0, "off_peak_multiplier": 1.0,
            "narrative_direction": "AI discussion", "agent_configs": [],
            "platform_config": {},
        }
        conn.execute(
            "INSERT INTO simulations (id, project_id, engine_type, platforms, config_json, status) "
            "VALUES (?, ?, 'claude', '[\"twitter\"]', ?, 'completed')",
            (sim_id, project_id, json.dumps(config)),
        )
        actions = [
            (sim_id, 1, 0, "alice", "CREATE_POST", json.dumps({"content": "AI is transforming everything"}), "twitter", "2026-01-01T00:00:00"),
            (sim_id, 1, 1, "bob", "CREATE_COMMENT", json.dumps({"post_id": 0, "content": "I agree!"}), "twitter", "2026-01-01T00:01:00"),
            (sim_id, 1, 1, "bob", "LIKE_POST", json.dumps({"post_id": 0}), "twitter", "2026-01-01T00:02:00"),
        ]
        for a in actions:
            conn.execute(
                "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", a,
            )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "AI researcher", "persona": "An AI researcher passionate about open science", "age": 30, "gender": "female", "profession": "Researcher", "interests": ["AI", "science"], "entity_type": "Person", "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Developer", "persona": "A pragmatic developer", "age": 28, "gender": "male", "profession": "Developer", "interests": ["coding"], "entity_type": "Person", "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestFullReportPipeline:
    def test_generate_then_chat(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_full_pipeline(tmp_db_path, tmp_data_dir)

        # Generate report
        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="# AI Trends Report\n\nAgents discussed AI transformation.",
            input_tokens=500, output_tokens=300, tool_calls=[],
        )

        result = generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim-int-1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert "AI Trends Report" in result.content_markdown

        # Chat with report
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="The agents discussed AI."),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        chat_events = list(report_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            report_id=result.report_id,
            message="Summarize the key themes",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        text = "".join(e.data for e in chat_events if e.type == "text_delta")
        assert "AI" in text

        # Chat with agent
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="As a researcher, I believe in open AI."),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        agent_events = list(agent_chat(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim-int-1",
            agent_id=0,
            message="What's your take on open-source AI?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        agent_text = "".join(e.data for e in agent_events if e.type == "text_delta")
        assert "open" in agent_text.lower()

    def test_chat_history_persists_across_turns(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_full_pipeline(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="# Report", input_tokens=100, output_tokens=50, tool_calls=[],
        )

        result = generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim-int-1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        # First chat turn
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="First response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])
        list(report_chat(
            db_path=tmp_db_path, data_dir=tmp_data_dir,
            report_id=result.report_id, message="Question 1",
            client=mock_client, domains_dir=tmp_domains_dir,
        ))

        # Second chat turn
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Second response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])
        list(report_chat(
            db_path=tmp_db_path, data_dir=tmp_data_dir,
            report_id=result.report_id, message="Question 2",
            client=mock_client, domains_dir=tmp_domains_dir,
        ))

        # Verify history has 4 messages (2 user + 2 assistant)
        with get_db(tmp_db_path) as conn:
            history = conn.execute(
                "SELECT * FROM chat_history WHERE conversation_id = ?",
                (result.report_id,),
            ).fetchall()
            assert len(history) == 4

        # Verify second call included history in messages
        call_args = mock_client.stream.call_args
        messages = call_args[1].get("messages", call_args[0][0] if call_args[0] else [])
        # Should have: prior user, prior assistant, new user = 3+ messages
        assert len(messages) >= 3
