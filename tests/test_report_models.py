"""Tests for report model dataclasses."""

from pathlib import Path
from unittest.mock import MagicMock

from forkcast.report.models import ReportResult, StreamEvent, ToolContext


class TestReportResult:
    def test_create_report_result(self):
        r = ReportResult(
            report_id="r1",
            simulation_id="s1",
            content_markdown="# Report",
            tool_rounds=3,
            tokens_used={"input": 100, "output": 200},
        )
        assert r.report_id == "r1"
        assert r.tool_rounds == 3

    def test_default_tokens(self):
        r = ReportResult(
            report_id="r1",
            simulation_id="s1",
            content_markdown="",
            tool_rounds=0,
        )
        assert r.tokens_used == {}


class TestStreamEvent:
    def test_text_delta(self):
        e = StreamEvent(type="text_delta", data="Hello")
        assert e.type == "text_delta"
        assert e.data == "Hello"

    def test_tool_use(self):
        e = StreamEvent(type="tool_use", data={"id": "t1", "name": "graph_search", "input": {"query": "AI"}})
        assert e.type == "tool_use"
        assert e.data["name"] == "graph_search"

    def test_done(self):
        e = StreamEvent(type="done", data={"input_tokens": 50, "output_tokens": 100, "stop_reason": "end_turn"})
        assert e.data["stop_reason"] == "end_turn"

    def test_error(self):
        e = StreamEvent(type="error", data="Something went wrong")
        assert e.type == "error"


class TestToolContext:
    def test_create_tool_context(self, tmp_path):
        ctx = ToolContext(
            db_path=tmp_path / "test.db",
            simulation_id="s1",
            project_id="p1",
            data_dir=tmp_path,
            graph=MagicMock(),
            chroma_collection=None,
            profiles=[],
            client=MagicMock(),
            domains_dir=tmp_path / "domains",
        )
        assert ctx.simulation_id == "s1"
        assert ctx.project_id == "p1"
