"""Tests for simulation data models."""

import json

from forkcast.simulation.models import AgentProfile, SimulationConfig, PrepareResult


class TestAgentProfile:
    def test_create_profile(self):
        profile = AgentProfile(
            agent_id=0,
            name="Jane Smith",
            username="jsmith",
            bio="AI researcher at MIT",
            persona="Dr. Jane Smith is a leading AI researcher...",
            age=35,
            gender="female",
            profession="AI Researcher",
            interests=["AI", "ethics", "policy"],
            entity_type="Researcher",
            entity_source="Dr. Jane Smith",
        )
        assert profile.agent_id == 0
        assert profile.name == "Jane Smith"
        assert profile.interests == ["AI", "ethics", "policy"]

    def test_profile_to_dict(self):
        profile = AgentProfile(
            agent_id=1,
            name="Test",
            username="test",
            bio="bio",
            persona="persona",
            age=30,
            gender="male",
            profession="Engineer",
            interests=["tech"],
            entity_type="Person",
            entity_source="Test Entity",
        )
        d = profile.to_dict()
        assert d["agent_id"] == 1
        assert d["entity_source"] == "Test Entity"
        assert isinstance(d, dict)

    def test_profiles_to_json(self):
        profiles = [
            AgentProfile(
                agent_id=i,
                name=f"Agent {i}",
                username=f"agent{i}",
                bio=f"Bio {i}",
                persona=f"Persona {i}",
                age=25 + i,
                gender="nonbinary",
                profession="Analyst",
                interests=["data"],
                entity_type="Person",
                entity_source=f"Entity {i}",
            )
            for i in range(3)
        ]
        json_str = json.dumps([p.to_dict() for p in profiles])
        parsed = json.loads(json_str)
        assert len(parsed) == 3
        assert parsed[0]["agent_id"] == 0
        assert parsed[2]["name"] == "Agent 2"


class TestSimulationConfig:
    def test_create_config(self):
        config = SimulationConfig(
            total_hours=48,
            minutes_per_round=30,
            peak_hours=[9, 10, 11, 12, 17, 18, 19],
            off_peak_hours=[0, 1, 2, 3, 4, 5],
            peak_multiplier=1.5,
            off_peak_multiplier=0.3,
            seed_posts=["Breaking: AI regulation proposed"],
            hot_topics=["AI regulation", "tech layoffs"],
            narrative_direction="Debate evolves from initial shock to nuanced policy discussion",
            agent_configs=[
                {"agent_id": 0, "activity_level": 0.8, "posts_per_hour": 2.0},
            ],
            platform_config={
                "feed_weights": {"recency": 0.4, "popularity": 0.4, "relevance": 0.2},
                "viral_threshold": 10,
                "echo_chamber_strength": 0.3,
            },
        )
        assert config.total_hours == 48
        assert len(config.seed_posts) == 1

    def test_config_to_dict(self):
        config = SimulationConfig(
            total_hours=24,
            minutes_per_round=15,
            peak_hours=[10, 11],
            off_peak_hours=[2, 3],
            peak_multiplier=1.2,
            off_peak_multiplier=0.5,
            seed_posts=["post"],
            hot_topics=["topic"],
            narrative_direction="direction",
            agent_configs=[],
            platform_config={},
        )
        d = config.to_dict()
        assert d["total_hours"] == 24
        assert isinstance(d["seed_posts"], list)


class TestSimulationConfigOptimizationFields:
    def test_config_has_decision_model_default(self):
        config = SimulationConfig(
            total_hours=2, minutes_per_round=30, peak_hours=[10],
            off_peak_hours=[0], peak_multiplier=1.5, off_peak_multiplier=0.3,
            seed_posts=[], hot_topics=[], narrative_direction="test",
            agent_configs=[], platform_config={},
        )
        assert config.decision_model == "claude-haiku-4-5"

    def test_config_has_creative_model_default(self):
        config = SimulationConfig(
            total_hours=2, minutes_per_round=30, peak_hours=[10],
            off_peak_hours=[0], peak_multiplier=1.5, off_peak_multiplier=0.3,
            seed_posts=[], hot_topics=[], narrative_direction="test",
            agent_configs=[], platform_config={},
        )
        assert config.creative_model == "claude-sonnet-4-6"

    def test_config_has_compress_feed_default_false(self):
        config = SimulationConfig(
            total_hours=2, minutes_per_round=30, peak_hours=[10],
            off_peak_hours=[0], peak_multiplier=1.5, off_peak_multiplier=0.3,
            seed_posts=[], hot_topics=[], narrative_direction="test",
            agent_configs=[], platform_config={},
        )
        assert config.compress_feed is False

    def test_config_to_dict_includes_new_fields(self):
        config = SimulationConfig(
            total_hours=2, minutes_per_round=30, peak_hours=[10],
            off_peak_hours=[0], peak_multiplier=1.5, off_peak_multiplier=0.3,
            seed_posts=[], hot_topics=[], narrative_direction="test",
            agent_configs=[], platform_config={},
            decision_model="custom-model", creative_model="custom-model-2",
            compress_feed=True,
        )
        d = config.to_dict()
        assert d["decision_model"] == "custom-model"
        assert d["creative_model"] == "custom-model-2"
        assert d["compress_feed"] is True


class TestPrepareResult:
    def test_create_result(self):
        result = PrepareResult(
            simulation_id="sim_abc123",
            profiles_count=10,
            profiles_path="/data/sim_abc123/profiles/agents.json",
            config_generated=True,
            tokens_used={"input": 5000, "output": 3000},
        )
        assert result.profiles_count == 10
        assert result.config_generated is True
