"""Tests for agent profile generation from graph entities."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from forkcast.llm.client import LLMResponse
from forkcast.llm.utils import strip_code_fences
from forkcast.simulation.models import AgentProfile
from forkcast.simulation.profile_generator import (
    generate_profile,
    generate_profiles,
    load_existing_profiles,
    save_profiles,
    _build_persona_prompt,
)


def _mock_client_for_profile():
    """Create a mock client that returns valid profile JSON."""
    client = MagicMock()
    client.default_model = "claude-sonnet-4-6"
    profile_json = json.dumps({
        "bio": "AI researcher specializing in ethics",
        "persona": "A cautious academic who values evidence-based discussion. "
                   "Tends to push back on hype with measured skepticism.",
        "age": 42,
        "gender": "female",
        "profession": "AI Ethics Researcher",
        "interests": ["AI safety", "policy", "philosophy"],
        "username": "dr_ethics",
        "name": "Dr. Sarah Chen",
    })
    client.smart_call.return_value = LLMResponse(
        text=profile_json,
        input_tokens=500,
        output_tokens=300,
    )
    return client


class TestStripCodeFences:
    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_no_fence_passthrough(self):
        text = '{"key": "value"}'
        assert strip_code_fences(text) == '{"key": "value"}'


class TestBuildPersonaPrompt:
    def test_includes_entity_info(self):
        entity = {
            "name": "OpenAI",
            "type": "Organization",
            "description": "AI research company",
        }
        prompt = _build_persona_prompt(
            entity=entity,
            related_entities=["Sam Altman", "Microsoft"],
            requirement="Predict AI regulation impact",
            persona_template="Entity: {{ entity_name }}\nType: {{ entity_type }}",
        )
        assert "OpenAI" in prompt
        assert "Organization" in prompt

    def test_includes_related_entities(self):
        entity = {"name": "Test", "type": "Person", "description": "desc"}
        prompt = _build_persona_prompt(
            entity=entity,
            related_entities=["Entity A", "Entity B"],
            requirement="question",
            persona_template="Related: {{ related_entities }}",
        )
        assert "Entity A" in prompt
        assert "Entity B" in prompt


class TestGenerateProfile:
    def test_generate_single_profile(self):
        client = _mock_client_for_profile()
        entity = {
            "name": "Dr. Sarah Chen",
            "type": "Researcher",
            "description": "AI ethics researcher at Stanford",
        }

        profile, tokens = generate_profile(
            client=client,
            entity=entity,
            agent_id=0,
            related_entities=["OpenAI", "MIT"],
            requirement="AI regulation impact",
            persona_template="Entity: {{ entity_name }}",
        )

        assert isinstance(profile, AgentProfile)
        assert profile.agent_id == 0
        assert profile.entity_type == "Researcher"
        assert profile.entity_source == "Dr. Sarah Chen"
        assert tokens["input"] == 500
        assert tokens["output"] == 300
        client.smart_call.assert_called_once()


class TestGenerateProfiles:
    def test_generate_multiple_profiles_with_incremental_save(self, tmp_path):
        client = _mock_client_for_profile()
        entities = [
            {"name": "Entity A", "type": "Person", "description": "desc A"},
            {"name": "Entity B", "type": "Organization", "description": "desc B"},
        ]
        graph_data = {
            "nodes": [
                {"id": "Entity A", "type": "Person"},
                {"id": "Entity B", "type": "Organization"},
            ],
            "edges": [
                {"source": "Entity A", "target": "Entity B", "type": "WORKS_AT"},
            ],
        }
        profiles_dir = tmp_path / "profiles"

        profiles, total_tokens = generate_profiles(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test question",
            persona_template="Entity: {{ entity_name }}",
            profiles_dir=profiles_dir,
        )

        assert len(profiles) == 2
        assert profiles[0].agent_id == 0
        assert profiles[1].agent_id == 1
        assert total_tokens["input"] == 1000  # 500 * 2
        assert total_tokens["output"] == 600  # 300 * 2
        # Verify incremental save — file should exist after generation
        agents_path = profiles_dir / "agents.json"
        assert agents_path.exists()
        saved = json.loads(agents_path.read_text())
        assert len(saved) == 2

    def test_skips_already_generated_profiles(self, tmp_path):
        """Incremental recovery: skips entities that already have profiles."""
        client = _mock_client_for_profile()
        entities = [
            {"name": "Entity A", "type": "Person", "description": "desc A"},
            {"name": "Entity B", "type": "Organization", "description": "desc B"},
        ]
        graph_data = {"nodes": [], "edges": []}
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir(parents=True)

        # Pre-existing profile for Entity A
        existing = [{"agent_id": 0, "name": "Entity A", "username": "entity_a",
                      "bio": "b", "persona": "p", "age": 30, "gender": "m",
                      "profession": "p", "interests": [], "entity_type": "Person",
                      "entity_source": "Entity A"}]
        (profiles_dir / "agents.json").write_text(json.dumps(existing))

        profiles, total_tokens = generate_profiles(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="q",
            persona_template="t",
            profiles_dir=profiles_dir,
        )

        # Should only generate 1 new profile (Entity B), not 2
        assert client.smart_call.call_count == 1
        assert len(profiles) == 2  # total includes existing + new
        assert total_tokens["input"] == 500  # only 1 API call

    def test_progress_callback(self, tmp_path):
        client = _mock_client_for_profile()
        entities = [
            {"name": "E1", "type": "Person", "description": "d1"},
            {"name": "E2", "type": "Person", "description": "d2"},
        ]
        graph_data = {"nodes": [], "edges": []}
        profiles_dir = tmp_path / "profiles"

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        generate_profiles(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="q",
            persona_template="t",
            on_progress=on_progress,
            profiles_dir=profiles_dir,
        )

        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)


class TestSaveAndLoadProfiles:
    def test_save_and_read_profiles(self, tmp_path):
        profiles = [
            AgentProfile(
                agent_id=0, name="A", username="a", bio="b", persona="p",
                age=30, gender="male", profession="dev", interests=["code"],
                entity_type="Person", entity_source="Entity A",
            ),
        ]
        profiles_dir = tmp_path / "profiles"
        path = save_profiles(profiles, profiles_dir)

        assert path.exists()
        loaded = json.loads(path.read_text())
        assert len(loaded) == 1
        assert loaded[0]["name"] == "A"

    def test_load_existing_profiles(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        data = [{"agent_id": 0, "entity_source": "Entity A"}]
        (profiles_dir / "agents.json").write_text(json.dumps(data))

        existing = load_existing_profiles(profiles_dir)
        assert "Entity A" in existing

    def test_load_nonexistent_returns_empty(self, tmp_path):
        existing = load_existing_profiles(tmp_path / "nope")
        assert existing == set()
