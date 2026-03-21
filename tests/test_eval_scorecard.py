"""Tests for scorecard assembly, persistence, and comparison."""

import json
from pathlib import Path

import pytest

from forkcast.eval.scorecard import assemble_scorecard, save_scorecard, load_scorecard, compare_scorecards


class TestAssembleScorecard:
    def test_assembles_with_all_gates_passed(self):
        gates = {
            "ontology.min_entity_types": {"passed": True, "value": 5, "threshold": 3},
            "ontology.valid_json": {"passed": True, "value": "valid"},
        }
        quality = {
            "ontology.specificity": {"score": 4, "justification": "Good"},
        }
        sc = assemble_scorecard(
            project_id="proj_1",
            simulation_id="sim_1",
            report_id="rpt_1",
            gates=gates,
            quality=quality,
        )
        assert sc["summary"]["gates_passed"] == 2
        assert sc["summary"]["gates_total"] == 2
        assert sc["summary"]["quality_avg"] == 4.0
        assert sc["summary"]["weakest"] == "ontology.specificity"
        assert "eval_id" in sc
        assert "timestamp" in sc

    def test_identifies_weakest_quality(self):
        gates = {}
        quality = {
            "a": {"score": 5, "justification": ""},
            "b": {"score": 2, "justification": ""},
            "c": {"score": 3, "justification": ""},
        }
        sc = assemble_scorecard("p", "s", "r", gates, quality)
        assert sc["summary"]["weakest"] == "b"

    def test_handles_empty_quality(self):
        sc = assemble_scorecard("p", "s", "r", {}, {})
        assert sc["summary"]["quality_avg"] == 0
        assert sc["summary"]["weakest"] is None


class TestSaveLoadScorecard:
    def test_round_trip(self, tmp_path):
        sc = assemble_scorecard("p", "s", "r", {"g1": {"passed": True}}, {"q1": {"score": 3, "justification": "ok"}})
        path = save_scorecard(sc, tmp_path)
        assert path.exists()
        loaded = load_scorecard(path)
        assert loaded["eval_id"] == sc["eval_id"]
        assert loaded["summary"] == sc["summary"]


class TestCompareScoreCards:
    def test_compare_shows_diff(self):
        sc1 = assemble_scorecard("p", "s", "r", {}, {"q1": {"score": 2, "justification": ""}})
        sc2 = assemble_scorecard("p", "s", "r", {}, {"q1": {"score": 4, "justification": ""}})
        diff = compare_scorecards(sc1, sc2)
        assert diff["quality_changes"]["q1"]["before"] == 2
        assert diff["quality_changes"]["q1"]["after"] == 4
        assert diff["quality_changes"]["q1"]["delta"] == 2
