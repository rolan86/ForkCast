"""Tests for evaluation gate functions (Layer 1)."""

import pytest

from forkcast.eval.gates import (
    gate_ontology_min_types,
    gate_ontology_valid_json,
    gate_persona_count_matches,
    gate_persona_required_fields,
    gate_persona_unique_names,
    gate_sim_min_actions,
    gate_sim_no_empty_rounds,
    gate_sim_action_diversity,
    gate_sim_all_agents_active,
    gate_sim_has_interactions,
    gate_sim_do_nothing_ratio,
    gate_report_min_length,
    gate_report_has_sections,
    gate_report_references_agents,
    gate_report_no_template_artifacts,
    gate_report_valid_markdown,
)


def _make_persona(name: str, username: str) -> dict:
    return {
        "name": name,
        "username": username,
        "bio": "A test bio.",
        "persona": "Curious and analytical.",
        "age": 30,
        "gender": "non-binary",
        "profession": "Engineer",
    }


# ---------------------------------------------------------------------------
# TestOntologyGates — 4 tests
# ---------------------------------------------------------------------------

class TestOntologyGates:
    def test_min_types_pass(self):
        ontology = {"entity_types": ["Person", "Organization", "Location"]}
        result = gate_ontology_min_types(ontology, threshold=3)
        assert result["passed"] is True
        assert result["value"] == 3
        assert result["threshold"] == 3

    def test_min_types_fail(self):
        ontology = {"entity_types": ["Person"]}
        result = gate_ontology_min_types(ontology, threshold=3)
        assert result["passed"] is False
        assert result["value"] == 1

    def test_valid_json_pass(self):
        result = gate_ontology_valid_json('{"entity_types": ["Person"]}')
        assert result["passed"] is True
        assert result["value"] == "valid"

    def test_valid_json_fail(self):
        result = gate_ontology_valid_json("{not valid json!!}")
        assert result["passed"] is False
        assert isinstance(result["value"], str)


# ---------------------------------------------------------------------------
# TestPersonaGates — 6 tests
# ---------------------------------------------------------------------------

class TestPersonaGates:
    def test_count_matches_pass(self):
        personas = [_make_persona("Alice", "alice"), _make_persona("Bob", "bob")]
        result = gate_persona_count_matches(personas, entity_count=2)
        assert result["passed"] is True
        assert result["value"] == 2

    def test_count_matches_fail(self):
        personas = [_make_persona("Alice", "alice")]
        result = gate_persona_count_matches(personas, entity_count=3)
        assert result["passed"] is False
        assert result["value"] == 1
        assert result["threshold"] == 3

    def test_required_fields_pass(self):
        personas = [_make_persona("Alice", "alice"), _make_persona("Bob", "bob")]
        result = gate_persona_required_fields(personas)
        assert result["passed"] is True

    def test_required_fields_fail(self):
        bad_persona = {"name": "Alice", "username": "alice"}  # missing fields
        result = gate_persona_required_fields([bad_persona])
        assert result["passed"] is False
        assert "missing" in result["value"]

    def test_unique_names_pass(self):
        personas = [_make_persona("Alice", "alice"), _make_persona("Bob", "bob")]
        result = gate_persona_unique_names(personas)
        assert result["passed"] is True

    def test_unique_names_fail(self):
        personas = [_make_persona("Alice", "alice"), _make_persona("Alice", "alice2")]
        result = gate_persona_unique_names(personas)
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# TestSimulationGates — 12 tests
# ---------------------------------------------------------------------------

class TestSimulationGates:
    def test_min_actions_pass(self):
        result = gate_sim_min_actions(total_actions=50, agent_count=10, round_count=5, factor=0.5)
        assert result["passed"] is True
        assert result["value"] == 50
        assert result["threshold"] == 25.0

    def test_min_actions_fail(self):
        result = gate_sim_min_actions(total_actions=5, agent_count=10, round_count=5, factor=0.5)
        assert result["passed"] is False

    def test_no_empty_rounds_pass(self):
        actions_per_round = {1: 5, 2: 3, 3: 7}
        result = gate_sim_no_empty_rounds(actions_per_round, total_rounds=3)
        assert result["passed"] is True

    def test_no_empty_rounds_fail(self):
        actions_per_round = {1: 5, 2: 0, 3: 7}
        result = gate_sim_no_empty_rounds(actions_per_round, total_rounds=3)
        assert result["passed"] is False
        assert "2" in result["value"]

    def test_action_diversity_pass(self):
        action_types = {"CREATE_POST": 10, "CREATE_COMMENT": 5, "LIKE_POST": 3, "DO_NOTHING": 2}
        result = gate_sim_action_diversity(action_types, threshold=3)
        assert result["passed"] is True
        assert result["value"] == 4

    def test_action_diversity_fail(self):
        action_types = {"CREATE_POST": 10, "DO_NOTHING": 5}
        result = gate_sim_action_diversity(action_types, threshold=3)
        assert result["passed"] is False
        assert result["value"] == 2

    def test_all_agents_active_pass(self):
        agent_actions = {0: 3, 1: 2, 2: 5}
        result = gate_sim_all_agents_active(agent_actions, expected_agents=3)
        assert result["passed"] is True

    def test_all_agents_active_fail(self):
        agent_actions = {0: 3, 1: 2}  # only 2 of 3 agents active
        result = gate_sim_all_agents_active(agent_actions, expected_agents=3)
        assert result["passed"] is False
        assert result["value"] == 2

    def test_has_interactions_pass(self):
        action_types = {"CREATE_POST": 5, "LIKE_POST": 3, "DO_NOTHING": 2}
        result = gate_sim_has_interactions(action_types)
        assert result["passed"] is True
        assert result["value"] == 3

    def test_has_interactions_fail(self):
        action_types = {"CREATE_POST": 5, "DO_NOTHING": 2}
        result = gate_sim_has_interactions(action_types)
        assert result["passed"] is False
        assert result["value"] == 0

    def test_do_nothing_ratio_pass(self):
        action_types = {"CREATE_POST": 8, "DO_NOTHING": 2}
        result = gate_sim_do_nothing_ratio(action_types, threshold=0.7)
        assert result["passed"] is True
        assert result["value"] == 0.2

    def test_do_nothing_ratio_fail(self):
        action_types = {"CREATE_POST": 2, "DO_NOTHING": 8}
        result = gate_sim_do_nothing_ratio(action_types, threshold=0.7)
        assert result["passed"] is False
        assert result["value"] == 0.8


# ---------------------------------------------------------------------------
# TestReportGates — 10 tests
# ---------------------------------------------------------------------------

class TestReportGates:
    _long_report = (
        "## Summary\n\nThis is a detailed summary of the simulation results.\n\n"
        "## Key Findings\n\nAgents Alice and Bob showed strong engagement patterns.\n\n"
        "## Predictions\n\nBased on the simulation data, we predict significant growth.\n\n"
        + "Additional content to ensure length. " * 10
    )

    def test_min_length_pass(self):
        result = gate_report_min_length(self._long_report, threshold=200)
        assert result["passed"] is True
        assert result["value"] >= 200

    def test_min_length_fail(self):
        result = gate_report_min_length("Short report.", threshold=500)
        assert result["passed"] is False
        assert result["value"] < 500

    def test_has_sections_pass(self):
        result = gate_report_has_sections(self._long_report, threshold=3)
        assert result["passed"] is True
        assert result["value"] >= 3

    def test_has_sections_fail(self):
        result = gate_report_has_sections("## Only one section\n\nSome text.", threshold=3)
        assert result["passed"] is False
        assert result["value"] == 1

    def test_references_agents_pass(self):
        report = "Alice made many posts. Bob replied frequently."
        result = gate_report_references_agents(report, agents=["Alice", "Bob", "Carol"])
        assert result["passed"] is True
        assert result["value"] >= 2

    def test_references_agents_fail(self):
        report = "The simulation showed interesting results overall."
        result = gate_report_references_agents(report, agents=["Alice", "Bob", "Carol"])
        assert result["passed"] is False
        assert result["value"] < 2

    def test_no_template_artifacts_pass(self):
        result = gate_report_no_template_artifacts("## Clean Report\n\nNo artifacts here.")
        assert result["passed"] is True

    def test_no_template_artifacts_fail_jinja(self):
        result = gate_report_no_template_artifacts("Hello {{ name }}, welcome!")
        assert result["passed"] is False
        assert "jinja=True" in result["value"]

    def test_no_template_artifacts_fail_placeholder(self):
        result = gate_report_no_template_artifacts("See [PLACEHOLDER] for details.")
        assert result["passed"] is False
        assert "placeholder=True" in result["value"]

    def test_valid_markdown_pass(self):
        result = gate_report_valid_markdown("## Title\n\n```python\nprint('hello')\n```\n")
        assert result["passed"] is True

    # Note: only 10 tests defined — last one counts as the unclosed fence fail
    def test_valid_markdown_fail_unclosed_fence(self):
        result = gate_report_valid_markdown("## Title\n\n```python\nprint('hello')\n")
        assert result["passed"] is False
        assert "odd fence count" in result["value"]
