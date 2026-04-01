"""Tests for two-phase model routing in Claude simulation engine."""

from forkcast.simulation.claude_engine import DECISION_TOOLS, CREATIVE_TOOLS, AGENT_TOOLS


class TestDecisionTools:
    def test_decision_tools_has_all_action_names(self):
        names = {t["name"] for t in DECISION_TOOLS}
        expected = {t["name"] for t in AGENT_TOOLS}
        assert names == expected

    def test_create_post_has_no_content_field(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "create_post")
        props = tool["input_schema"]["properties"]
        assert "content" not in props

    def test_create_comment_has_post_id_but_no_content(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "create_comment")
        props = tool["input_schema"]["properties"]
        assert "post_id" in props
        assert "content" not in props

    def test_do_nothing_keeps_reason_field(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "do_nothing")
        props = tool["input_schema"]["properties"]
        assert "reason" in props

    def test_like_post_unchanged(self):
        decision = next(t for t in DECISION_TOOLS if t["name"] == "like_post")
        original = next(t for t in AGENT_TOOLS if t["name"] == "like_post")
        assert decision["input_schema"] == original["input_schema"]


class TestCreativeTools:
    def test_has_write_content_tool(self):
        names = {t["name"] for t in CREATIVE_TOOLS}
        assert "write_content" in names

    def test_write_content_has_content_field(self):
        tool = next(t for t in CREATIVE_TOOLS if t["name"] == "write_content")
        props = tool["input_schema"]["properties"]
        assert "content" in props
        assert props["content"]["type"] == "string"
