"""Tests for enhanced SSE progress events during preparation."""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from forkcast.simulation.profile_generator import generate_profiles_batched


class TestProfileProgressEvents:
    """Verify per-profile progress callback includes agent data."""

    def test_on_profile_callback_receives_agent_name_and_bio(self):
        """The on_profile callback should fire per profile with name and bio."""
        received = []

        def on_profile(stage, **kwargs):
            received.append(kwargs)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "name": "Dr. Sarah Chen",
                "username": "sarahchen",
                "bio": "AI researcher at Stanford",
                "persona": "Cautious optimist",
                "age": 38,
                "gender": "female",
                "profession": "AI Researcher",
                "interests": ["machine learning"],
            }
        ])
        mock_response.input_tokens = 100
        mock_response.output_tokens = 200
        mock_client.complete.return_value = mock_response

        entities = [{"name": "Sarah Chen", "type": "Person", "description": "AI researcher"}]
        graph_data = {"nodes": entities, "edges": []}

        with patch("forkcast.simulation.profile_generator.save_profiles"):
            profiles, _ = generate_profiles_batched(
                client=mock_client,
                entities=entities,
                graph_data=graph_data,
                requirement="Test question",
                persona_batch_template="{{entities}}",
                profiles_dir=Path("/tmp/test_profiles"),
                on_progress=on_profile,
                model="test-model",
            )

        profile_events = [e for e in received if e.get("agent_name")]
        assert len(profile_events) >= 1
        assert profile_events[0]["agent_name"] == "@sarahchen"
        assert "AI researcher" in profile_events[0]["agent_bio"]
