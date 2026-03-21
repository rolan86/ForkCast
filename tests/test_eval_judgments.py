"""Tests for LLM quality judgment functions (Layer 2)."""

import json
from unittest.mock import MagicMock

from forkcast.eval.judgments import run_judgment, load_rubric, JUDGMENT_NAMES


class TestLoadRubric:
    def test_loads_existing_rubric(self):
        rubric = load_rubric("ontology_specificity")
        assert len(rubric) > 50
        assert "score" in rubric.lower() or "rating" in rubric.lower()

    def test_all_rubric_files_exist(self):
        for name in JUDGMENT_NAMES:
            rubric = load_rubric(name)
            assert len(rubric) > 0, f"Rubric for {name} is empty"


class TestRunJudgment:
    def test_returns_score_and_justification(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text='{"score": 4, "justification": "Good quality output"}'
        )
        result = run_judgment(
            client=mock_client,
            judgment_name="ontology_specificity",
            content="Some ontology output to evaluate",
        )
        assert result["score"] == 4
        assert "Good quality" in result["justification"]

    def test_handles_malformed_llm_response(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(text="not json at all")
        result = run_judgment(
            client=mock_client,
            judgment_name="ontology_specificity",
            content="Some content",
        )
        assert result["score"] == 0
        assert "parse" in result["justification"].lower() or "error" in result["justification"].lower()
