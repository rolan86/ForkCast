"""Tests for smart agent suggestion."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse


def _setup_suggest(db_path, data_dir, sim_id="sim1"):
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
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "AI researcher",
         "persona": "Curious researcher who loves AI", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI", "ML"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Traditional plumber",
         "persona": "Skeptical of technology", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestSuggestAgents:
    def test_returns_ranked_suggestions(self, tmp_db_path, tmp_data_dir):
        _setup_suggest(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.complete.return_value = LLMResponse(
            text=json.dumps({
                "suggestions": [
                    {"agent_id": 0, "reason": "AI expert — most relevant"},
                    {"agent_id": 1, "reason": "Skeptic perspective — useful contrast"},
                ]
            }),
            input_tokens=100,
            output_tokens=50,
        )

        from forkcast.interaction.suggest import suggest_agents

        result = suggest_agents(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            topic="AI trust",
            client=mock_client,
        )

        assert "suggestions" in result
        assert len(result["suggestions"]) == 2
        assert result["suggestions"][0]["agent_id"] == 0
