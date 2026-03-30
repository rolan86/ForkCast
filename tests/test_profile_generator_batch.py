"""Tests for batched profile generation functions."""

import json
from pathlib import Path
from unittest.mock import MagicMock, call

from forkcast.llm.client import LLMResponse
from forkcast.simulation.models import AgentProfile
from forkcast.simulation.profile_generator import (
    _generate_batch,
    _generate_single_fallback,
    generate_profiles_batched,
)


def _make_mock_client(batch_responses: list[str]):
    client = MagicMock()
    client.default_model = "claude-sonnet-4-6"
    client.complete.side_effect = [
        LLMResponse(text=text, input_tokens=1000, output_tokens=2000)
        for text in batch_responses
    ]
    return client


def _make_entities(count: int):
    return [
        {"name": f"Entity_{i}", "type": "Organization", "description": f"Description {i}"}
        for i in range(count)
    ]


def _make_graph_data(entities):
    return {
        "nodes": [{"id": e["name"], "type": e["type"]} for e in entities],
        "edges": [{"source": entities[0]["name"], "target": entities[1]["name"], "type": "RELATED"}]
        if len(entities) >= 2 else [],
    }


def _batch_response(count: int):
    return json.dumps([
        {
            "name": f"Person {i}", "username": f"person_{i}",
            "bio": f"Bio for person {i}", "persona": f"Detailed persona for person {i}",
            "age": 30 + i, "gender": "female" if i % 2 == 0 else "male",
            "profession": f"Profession {i}", "interests": [f"interest_{i}_a", f"interest_{i}_b"],
        }
        for i in range(count)
    ])


class TestGenerateBatch:
    def test_generate_batch_returns_correct_profiles(self):
        entities = _make_entities(3)
        client = _make_mock_client([_batch_response(3)])

        profiles, tokens = _generate_batch(
            client=client,
            entities=entities,
            requirement="Test requirement",
            template="Generate {{ count }} profiles for: {% for e in entities %}{{ e.name }}{% endfor %}",
            start_agent_id=5,
        )

        assert len(profiles) == 3
        assert profiles[0].agent_id == 5
        assert profiles[1].agent_id == 6
        assert profiles[2].agent_id == 7
        assert profiles[0].entity_source == "Entity_0"
        assert profiles[1].entity_source == "Entity_1"
        assert profiles[2].entity_source == "Entity_2"
        assert profiles[0].entity_type == "Organization"
        assert tokens == {"input": 1000, "output": 2000}

    def test_generate_batch_uses_complete_not_smart_call(self):
        entities = _make_entities(2)
        client = _make_mock_client([_batch_response(2)])

        _generate_batch(
            client=client,
            entities=entities,
            requirement="Test",
            template="Generate {{ count }} profiles.",
        )

        client.complete.assert_called_once()
        client.smart_call.assert_not_called()

    def test_generate_batch_sets_max_tokens_16000(self):
        entities = _make_entities(2)
        client = _make_mock_client([_batch_response(2)])

        _generate_batch(
            client=client,
            entities=entities,
            requirement="Test",
            template="Generate {{ count }} profiles.",
        )

        _, kwargs = client.complete.call_args
        assert kwargs["max_tokens"] == 16000


class TestGenerateSingleFallback:
    def test_fallback_uses_complete_not_smart_call(self):
        entity = {"name": "TestEntity", "type": "Person", "description": "A test entity"}
        single_response = json.dumps({
            "name": "Test Person", "username": "test_person",
            "bio": "A bio", "persona": "A persona",
            "age": 35, "gender": "male",
            "profession": "Engineer", "interests": ["coding"],
        })
        client = _make_mock_client([single_response])

        profile, tokens = _generate_single_fallback(
            client=client,
            entity=entity,
            requirement="Test requirement",
            persona_template="Entity: {{ entity_name }}\nType: {{ entity_type }}",
            agent_id=0,
        )

        client.complete.assert_called_once()
        client.smart_call.assert_not_called()
        assert isinstance(profile, AgentProfile)
        assert profile.name == "Test Person"


class TestGenerateProfilesBatched:
    def test_batches_entities_correctly(self, tmp_path):
        entities = _make_entities(8)
        graph_data = _make_graph_data(entities)
        profiles_dir = tmp_path / "profiles"

        # 3 batches: 3 + 3 + 2
        client = _make_mock_client([
            _batch_response(3),
            _batch_response(3),
            _batch_response(2),
        ])

        profiles, token_records = generate_profiles_batched(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test",
            persona_batch_template="Generate {{ count }} profiles for: {% for e in entities %}{{ e.name }}{% endfor %}",
            profiles_dir=profiles_dir,
            batch_size=3,
        )

        assert len(profiles) == 8
        assert client.complete.call_count == 3
        # Sequential agent_ids
        for i, profile in enumerate(profiles):
            assert profile.agent_id == i

    def test_incremental_save_after_each_batch(self, tmp_path):
        entities = _make_entities(4)
        graph_data = _make_graph_data(entities)
        profiles_dir = tmp_path / "profiles"

        client = _make_mock_client([
            _batch_response(2),
            _batch_response(2),
        ])

        profiles, _ = generate_profiles_batched(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test",
            persona_batch_template="Generate {{ count }} profiles.",
            profiles_dir=profiles_dir,
            batch_size=2,
        )

        agents_path = profiles_dir / "agents.json"
        assert agents_path.exists()
        saved = json.loads(agents_path.read_text())
        assert len(saved) == 4

    def test_skips_already_generated_profiles(self, tmp_path):
        entities = _make_entities(4)
        graph_data = _make_graph_data(entities)
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir(parents=True)

        # Pre-existing profiles for Entity_0 and Entity_1
        existing = [
            {"agent_id": 0, "name": "Person 0", "username": "person_0",
             "bio": "b", "persona": "p", "age": 30, "gender": "m",
             "profession": "p", "interests": [], "entity_type": "Organization",
             "entity_source": "Entity_0"},
            {"agent_id": 1, "name": "Person 1", "username": "person_1",
             "bio": "b", "persona": "p", "age": 31, "gender": "f",
             "profession": "p", "interests": [], "entity_type": "Organization",
             "entity_source": "Entity_1"},
        ]
        (profiles_dir / "agents.json").write_text(json.dumps(existing))

        # Only 2 remaining entities → 1 batch
        client = _make_mock_client([_batch_response(2)])

        profiles, token_records = generate_profiles_batched(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test",
            persona_batch_template="Generate {{ count }} profiles.",
            profiles_dir=profiles_dir,
            batch_size=3,
        )

        assert client.complete.call_count == 1
        assert len(profiles) == 4  # 2 existing + 2 new

    def test_progress_callback(self, tmp_path):
        entities = _make_entities(4)
        graph_data = _make_graph_data(entities)
        profiles_dir = tmp_path / "profiles"

        client = _make_mock_client([
            _batch_response(2),
            _batch_response(2),
        ])

        progress_calls = []

        def on_progress(event_type, **kwargs):
            progress_calls.append((event_type, kwargs))

        generate_profiles_batched(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test",
            persona_batch_template="Generate {{ count }} profiles.",
            profiles_dir=profiles_dir,
            on_progress=on_progress,
            batch_size=2,
        )

        assert len(progress_calls) == 2
        assert progress_calls[0] == ("profile_batch", {
            "batch": 1, "total_batches": 2,
            "input_tokens": 1000, "output_tokens": 2000,
        })
        assert progress_calls[1] == ("profile_batch", {
            "batch": 2, "total_batches": 2,
            "input_tokens": 1000, "output_tokens": 2000,
        })

    def test_fallback_on_wrong_count(self, tmp_path):
        entities = _make_entities(3)
        graph_data = _make_graph_data(entities)
        profiles_dir = tmp_path / "profiles"

        # Batch returns only 2 profiles instead of 3, then fallback generates 1
        fallback_response = json.dumps({
            "name": "Fallback Person", "username": "fallback_person",
            "bio": "Fallback bio", "persona": "Fallback persona",
            "age": 40, "gender": "female",
            "profession": "Analyst", "interests": ["analysis"],
        })
        client = _make_mock_client([
            _batch_response(2),  # batch returns 2 instead of 3
            fallback_response,   # fallback for the missing one
        ])

        profiles, token_records = generate_profiles_batched(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement="Test",
            persona_batch_template="Generate {{ count }} profiles for: {% for e in entities %}{{ e.name }}{% endfor %}",
            profiles_dir=profiles_dir,
            batch_size=3,
        )

        assert len(profiles) == 3
        assert client.complete.call_count == 2  # 1 batch + 1 fallback
