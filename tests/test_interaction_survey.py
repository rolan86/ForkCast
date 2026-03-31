"""Tests for survey and poll interactions."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.report.models import StreamEvent


def _setup_survey(db_path, data_dir, sim_id="sim1"):
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
         "persona": "Researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Test",
         "persona": "Plumber", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestSurvey:
    def test_streams_agent_responses_and_summary(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_survey(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        # stream returns per-agent responses — use side_effect for fresh iterators
        mock_client.stream.side_effect = lambda **kwargs: iter([
            StreamEvent(type="text_delta", data="My answer"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])
        # complete returns summary
        mock_client.complete.return_value = LLMResponse(
            text="Theme: everyone wants transparency",
            input_tokens=100, output_tokens=50,
        )

        from forkcast.interaction.survey import free_text_survey

        events = list(free_text_survey(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            question="What matters most?",
            agent_ids=None,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        agent_done = [e for e in events if e.type == "agent_done"]
        assert len(agent_done) == 2
        summary = [e for e in events if e.type == "summary"]
        assert len(summary) == 1


class TestPoll:
    def test_returns_structured_results(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_survey(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.complete.side_effect = [
            LLMResponse(
                text=json.dumps({"choice": "Yes", "reasoning": "I love AI"}),
                input_tokens=10, output_tokens=20,
            ),
            LLMResponse(
                text=json.dumps({"choice": "No", "reasoning": "Too risky"}),
                input_tokens=10, output_tokens=20,
            ),
        ]

        from forkcast.interaction.poll import structured_poll

        result = structured_poll(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            question="Adopt AI?",
            options=["Yes", "No", "Maybe"],
            agent_ids=None,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert "results" in result
        assert len(result["results"]) == 2
        assert "summary" in result
        assert result["summary"]["Yes"] == 1
        assert result["summary"]["No"] == 1
