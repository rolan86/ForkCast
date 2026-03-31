"""Tests for debate interaction."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.report.models import StreamEvent


def _setup_debate(db_path, data_dir, sim_id="sim1"):
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
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Pro AI",
         "persona": "AI advocate", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Anti AI",
         "persona": "AI skeptic", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestDebate:
    def test_autoplay_runs_all_rounds(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_debate(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        # Need side_effect for fresh iterators per call (4 calls: 2 rounds x 2 agents)
        mock_client.stream.side_effect = lambda **kwargs: iter([
            StreamEvent(type="text_delta", data="My argument"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.debate import run_debate

        events = list(run_debate(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id_pro=0,
            agent_id_con=1,
            topic="Should AI replace bookkeepers?",
            rounds=2,
            mode="autoplay",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        round_starts = [e for e in events if e.type == "round_start"]
        round_ends = [e for e in events if e.type == "round_end"]
        assert len(round_starts) == 2
        assert len(round_ends) == 2

        agent_done = [e for e in events if e.type == "agent_done"]
        assert len(agent_done) == 4  # 2 agents x 2 rounds

        complete = [e for e in events if e.type == "complete"]
        assert len(complete) == 1
