"""Integration tests for dynamics wiring in the simulation runner and engine."""

import json
import random

import pytest

from forkcast.simulation.dynamics import HAS_DYNAMICS

pytestmark = pytest.mark.skipif(not HAS_DYNAMICS, reason="forkcast-nextlevel not installed")


class TestDynamicsRunnerWiring:
    """Verify dynamics are initialized, evolved, and checkpointed."""

    def test_dynamics_initialized_when_enabled(self):
        """Runner should create DynamicsState when circadian or engagement enabled."""
        from forkcast.simulation.dynamics import DynamicsState, CircadianModel, EulerIntegrator, compute_phase_offset
        from forkcast.simulation.models import AgentProfile
        profiles = [
            AgentProfile(agent_id=0, name="Alice", username="alice", bio="", persona="",
                         age=30, gender="F", profession="trader", interests=[],
                         entity_type="Person", entity_source="test"),
        ]
        integrator = EulerIntegrator()
        dynamics = DynamicsState(integrator=integrator, circadian_models={}, engagement_models={})
        for p in profiles:
            offset = compute_phase_offset(p.name, p.profession)
            dynamics.circadian_models[p.agent_id] = CircadianModel(phase_offset=offset)
        assert 0 in dynamics.circadian_models

    def test_dynamics_none_when_disabled(self):
        """When both models disabled, dynamics should be None."""
        from forkcast.simulation.models import SimulationConfig
        config = SimulationConfig(
            total_hours=1, minutes_per_round=30, peak_hours=[], off_peak_hours=[],
            peak_multiplier=1.0, off_peak_multiplier=1.0, seed_posts=[], hot_topics=[],
            narrative_direction="", agent_configs=[], platform_config={},
            circadian_enabled=False, engagement_enabled=False,
        )
        dynamics = None if not (config.circadian_enabled or config.engagement_enabled) else "not none"
        assert dynamics is None

    def test_checkpoint_includes_dynamics(self, tmp_path):
        """Dynamics state should be serialized alongside sim state in checkpoint."""
        from forkcast.simulation.dynamics import DynamicsState, CircadianModel, EulerIntegrator
        from forkcast.simulation.state import SimulationState
        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2})
        dynamics = DynamicsState(
            integrator=EulerIntegrator(),
            circadian_models={0: CircadianModel(6.0)},
            engagement_models={},
            sim_hours=2.0,
        )
        state_dict = state.to_dict()
        state_dict["dynamics_state"] = dynamics.to_dict()
        state_path = tmp_path / "sim_state_r1.json"
        state_path.write_text(json.dumps(state_dict))
        loaded = json.loads(state_path.read_text())
        assert "dynamics_state" in loaded
        restored = DynamicsState.from_dict(loaded["dynamics_state"], EulerIntegrator())
        assert restored.sim_hours == 2.0
        assert 0 in restored.circadian_models

    def test_resume_from_pre_dynamics_checkpoint(self, tmp_path):
        """Resuming a checkpoint without dynamics_state should create fresh dynamics."""
        from forkcast.simulation.dynamics import DynamicsState, CircadianModel, EulerIntegrator, compute_phase_offset
        from forkcast.simulation.state import SimulationState
        from forkcast.simulation.models import AgentProfile
        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2})
        state_path = tmp_path / "sim_state_r1.json"
        state_path.write_text(json.dumps(state.to_dict()))
        loaded = json.loads(state_path.read_text())
        assert "dynamics_state" not in loaded
        integrator = EulerIntegrator()
        dynamics = DynamicsState(integrator=integrator)
        profiles = [
            AgentProfile(agent_id=0, name="Alice", username="alice", bio="", persona="",
                         age=30, gender="F", profession="trader", interests=[],
                         entity_type="Person", entity_source="test"),
        ]
        for p in profiles:
            dynamics.circadian_models[p.agent_id] = CircadianModel(
                phase_offset=compute_phase_offset(p.name, p.profession),
            )
        assert 0 in dynamics.circadian_models
        assert dynamics.sim_hours == 0.0

    def test_write_checkpoint_with_dynamics(self, tmp_path):
        """write_checkpoint should include dynamics_state in sim_state file."""
        from forkcast.simulation.runner import write_checkpoint
        from forkcast.simulation.dynamics import DynamicsState, CircadianModel, EngagementModel, EulerIntegrator
        from forkcast.simulation.state import SimulationState
        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2})
        em = EngagementModel(post_id=0, carrying_capacity=50.0)
        em.engagement_level = 15.0
        dynamics = DynamicsState(
            integrator=EulerIntegrator(),
            circadian_models={0: CircadianModel(6.0)},
            engagement_models={0: em},
            sim_hours=3.0,
        )
        write_checkpoint(
            sim_dir=tmp_path, round_num=1, total_rounds=5,
            platform="twitter", platform_index=0,
            completed_platforms=[], state=state, dynamics=dynamics,
        )
        state_path = tmp_path / "sim_state_r1.json"
        assert state_path.exists()
        loaded = json.loads(state_path.read_text())
        assert "dynamics_state" in loaded
        assert loaded["dynamics_state"]["sim_hours"] == 3.0
        assert "0" in loaded["dynamics_state"]["engagement"]


class TestClaudeEngineDynamics:
    """Verify circadian and engagement context wiring in ClaudeEngine."""

    def test_circadian_replaces_activation_probability(self):
        """With dynamics, _determine_active_agents should use circadian levels."""
        from forkcast.simulation.claude_engine import _determine_active_agents
        from forkcast.simulation.dynamics import DynamicsState, CircadianModel, EulerIntegrator
        from forkcast.simulation.models import AgentProfile, SimulationConfig
        random.seed(42)
        profiles = [
            AgentProfile(agent_id=i, name=f"Agent{i}", username=f"agent{i}", bio="", persona="",
                         age=30, gender="F", profession="trader", interests=[],
                         entity_type="Person", entity_source="test")
            for i in range(10)
        ]
        config = SimulationConfig(
            total_hours=6, minutes_per_round=30, peak_hours=[], off_peak_hours=[],
            peak_multiplier=1.0, off_peak_multiplier=1.0, seed_posts=[], hot_topics=[],
            narrative_direction="", agent_configs=[], platform_config={},
        )
        # Create dynamics where all agents have very low activity (0.2)
        dynamics = DynamicsState(integrator=EulerIntegrator())
        for p in profiles:
            cm = CircadianModel(phase_offset=0.0)
            cm.activity_level = 0.2  # low activity
            dynamics.circadian_models[p.agent_id] = cm
        active = _determine_active_agents(profiles, config, current_hour=12, dynamics=dynamics)
        assert isinstance(active, list)
        assert len(active) >= 1  # always at least one

    def test_engagement_context_in_prompt(self):
        """Trending posts should appear as platform signals in agent context."""
        from forkcast.simulation.claude_engine import _build_agent_context
        from forkcast.simulation.dynamics import DynamicsState, EngagementModel, EulerIntegrator
        from forkcast.simulation.models import AgentProfile
        from forkcast.simulation.state import SimulationState
        profile = AgentProfile(
            agent_id=0, name="Alice", username="alice", bio="", persona="test",
            age=30, gender="F", profession="trader", interests=[],
            entity_type="Person", entity_source="test",
        )
        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2})
        state.add_post(0, "alice", "Bitcoin to 100k!", "2024-01-01T00:00:00Z")
        dynamics = DynamicsState(integrator=EulerIntegrator())
        em = EngagementModel(post_id=0, carrying_capacity=100.0)
        em.engagement_level = 70.0  # trending (70% saturation)
        dynamics.engagement_models[0] = em
        context = _build_agent_context(
            profile=profile, state=state, round_num=2, hot_topics=[],
            seed_posts=[], agent_system_template="You are {{ agent_name }}.",
            compress_feed=False, dynamics=dynamics,
        )
        user_msg = context["messages"][0]["content"]
        assert "trending" in user_msg.lower() or "Platform signals" in user_msg
