"""Tests for report agent tools."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.report.models import ToolContext
from forkcast.report.tools import (
    REPORT_TOOLS,
    tool_agent_actions,
    tool_graph_explore,
    tool_graph_search,
    tool_interview_agent,
    tool_simulation_data,
)
from forkcast.simulation.models import AgentProfile


def _make_profile(agent_id=0, name="Alice", username="alice"):
    return AgentProfile(
        agent_id=agent_id, name=name, username=username,
        bio="Test", persona="A test agent", age=30, gender="female",
        profession="Tester", interests=["testing"], entity_type="Person",
        entity_source="test",
    )


def _make_context(tmp_path, db_path=None, profiles=None, graph=None, client=None):
    if db_path is None:
        db_path = tmp_path / "test.db"
    init_db(db_path)
    if graph is None:
        graph = nx.DiGraph()
    return ToolContext(
        db_path=db_path,
        simulation_id="sim1",
        project_id="proj1",
        data_dir=tmp_path,
        graph=graph,
        chroma_collection=None,
        profiles=profiles or [_make_profile()],
        client=client or MagicMock(),
        domains_dir=tmp_path / "domains",
    )


def _insert_actions(db_path, simulation_id="sim1"):
    """Insert sample simulation actions for testing."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status) VALUES (?, 'proj1', 'completed')",
            (simulation_id,),
        )
        actions = [
            (simulation_id, 1, 0, "alice", "CREATE_POST", json.dumps({"content": "Hello world"}), "twitter", "2026-01-01T00:00:00"),
            (simulation_id, 1, 1, "bob", "LIKE_POST", json.dumps({"post_id": 0}), "twitter", "2026-01-01T00:01:00"),
            (simulation_id, 1, 1, "bob", "CREATE_COMMENT", json.dumps({"post_id": 0, "content": "Nice!"}), "twitter", "2026-01-01T00:02:00"),
            (simulation_id, 2, 0, "alice", "CREATE_POST", json.dumps({"content": "Second post"}), "twitter", "2026-01-01T01:00:00"),
            (simulation_id, 2, 1, "bob", "DO_NOTHING", json.dumps({"reason": "bored"}), "twitter", "2026-01-01T01:01:00"),
        ]
        for a in actions:
            conn.execute(
                "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", a,
            )


class TestToolSchemas:
    def test_report_tools_is_list(self):
        assert isinstance(REPORT_TOOLS, list)
        assert len(REPORT_TOOLS) == 5

    def test_each_tool_has_required_fields(self):
        for tool in REPORT_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_tool_names(self):
        names = {t["name"] for t in REPORT_TOOLS}
        assert names == {"graph_search", "graph_explore", "simulation_data", "interview_agent", "agent_actions"}


class TestGraphExplore:
    def test_explore_entity_neighbors(self, tmp_path):
        g = nx.DiGraph()
        g.add_node("Llama", type="AIModel", description="Open-source model")
        g.add_node("Mistral", type="AIModel", description="European model")
        g.add_node("DevCommunity", type="Community", description="Developers")
        g.add_edge("Llama", "Mistral", type="COMPETES_WITH", fact="Both open-source")
        g.add_edge("DevCommunity", "Llama", type="ADOPTS", fact="Devs use Llama")

        ctx = _make_context(tmp_path, graph=g)
        result = tool_graph_explore(ctx, entity_name="Llama", depth=1)
        assert "Mistral" in str(result)
        assert "DevCommunity" in str(result)

    def test_explore_unknown_entity(self, tmp_path):
        ctx = _make_context(tmp_path, graph=nx.DiGraph())
        result = tool_graph_explore(ctx, entity_name="NonExistent", depth=1)
        assert "not found" in str(result).lower()


class TestGraphSearch:
    def test_search_with_collection(self, tmp_path):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["e1"]],
            "documents": [["Llama is open-source"]],
            "metadatas": [[{"type": "entity"}]],
            "distances": [[0.1]],
        }
        ctx = _make_context(tmp_path)
        ctx.chroma_collection = mock_collection
        result = tool_graph_search(ctx, query="open source AI", n_results=3)
        assert len(result) == 1
        assert result[0]["text"] == "Llama is open-source"

    def test_search_without_collection(self, tmp_path):
        ctx = _make_context(tmp_path)
        ctx.chroma_collection = None
        result = tool_graph_search(ctx, query="test", n_results=3)
        assert result == [] or "unavailable" in str(result).lower()


class TestSimulationData:
    def test_summary(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_simulation_data(ctx, query_type="summary")
        assert result["total_actions"] == 5
        assert "CREATE_POST" in result["action_counts"]

    def test_agent_activity(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_simulation_data(ctx, query_type="agent_activity")
        assert len(result) >= 2

    def test_action_counts(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_simulation_data(ctx, query_type="action_counts")
        assert result["CREATE_POST"] == 2

    def test_timeline(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_simulation_data(ctx, query_type="timeline")
        assert len(result) == 2

    def test_top_posts(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_simulation_data(ctx, query_type="top_posts")
        assert len(result) >= 1


class TestAgentActions:
    def test_get_all_actions(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_agent_actions(ctx, agent_id=0)
        assert len(result) == 2

    def test_filter_by_type(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_agent_actions(ctx, agent_id=1, action_type="LIKE_POST")
        assert len(result) == 1

    def test_unknown_agent(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)
        ctx = _make_context(tmp_path, db_path=db_path)
        result = tool_agent_actions(ctx, agent_id=999)
        assert len(result) == 0


class TestInterviewAgent:
    def test_interview_returns_response(self, tmp_path):
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text="I think AI should be open.", input_tokens=50, output_tokens=30,
        )
        profile = _make_profile(agent_id=0)
        db_path = tmp_path / "test.db"
        _insert_actions(db_path)

        domains_dir = tmp_path / "domains" / "_default" / "prompts"
        domains_dir.mkdir(parents=True)
        (domains_dir.parent / "manifest.yaml").write_text(
            "name: _default\nversion: '1.0'\ndescription: Test\nlanguage: en\nsim_engine: claude\nplatforms: [twitter]\n"
            "prompts:\n  agent_system: prompts/agent_system.md\n"
        )
        (domains_dir / "agent_system.md").write_text("You are {{ agent_name }}. {{ persona }}")
        for p in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
            (domains_dir / p).write_text(f"# {p}\nPlaceholder.\n")

        ctx = _make_context(tmp_path, db_path=db_path, profiles=[profile], client=mock_client)
        ctx.domains_dir = tmp_path / "domains"
        result = tool_interview_agent(ctx, agent_id=0, question="What do you think about AI?")
        assert "open" in result.lower()
        mock_client.complete.assert_called_once()

    def test_interview_unknown_agent(self, tmp_path):
        ctx = _make_context(tmp_path, profiles=[_make_profile()])
        result = tool_interview_agent(ctx, agent_id=999, question="Hello?")
        assert "not found" in result.lower()
