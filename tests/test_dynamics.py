"""Tests for dynamics config fields and carrying capacity."""

import pytest


# ---------------------------------------------------------------------------
# TestSimulationConfigDynamics
# ---------------------------------------------------------------------------

class TestSimulationConfigDynamics:
    def test_default_dynamics_fields(self):
        """New dynamics fields should have sensible defaults."""
        from forkcast.simulation.models import SimulationConfig
        config = SimulationConfig(
            total_hours=6, minutes_per_round=30, peak_hours=[9,10,11],
            off_peak_hours=[0,1,2], peak_multiplier=1.5, off_peak_multiplier=0.5,
            seed_posts=[], hot_topics=[], narrative_direction="",
            agent_configs=[], platform_config={},
        )
        assert config.circadian_enabled is True
        assert config.engagement_enabled is True
        assert config.integrator_method == "euler"
        assert config.integrator_order == 4
        assert config.integrator_tolerance == 1e-6
        assert config.integrator_max_order == 8

    def test_dynamics_fields_in_to_dict(self):
        """to_dict should include all dynamics fields."""
        from forkcast.simulation.models import SimulationConfig
        config = SimulationConfig(
            total_hours=6, minutes_per_round=30, peak_hours=[9,10,11],
            off_peak_hours=[0,1,2], peak_multiplier=1.5, off_peak_multiplier=0.5,
            seed_posts=[], hot_topics=[], narrative_direction="",
            agent_configs=[], platform_config={},
            integrator_method="rk", integrator_order=8,
        )
        d = config.to_dict()
        assert d["circadian_enabled"] is True
        assert d["integrator_method"] == "rk"
        assert d["integrator_order"] == 8


# ---------------------------------------------------------------------------
# TestCarryingCapacity
# ---------------------------------------------------------------------------

class TestCarryingCapacity:
    def test_base_scales_with_agents(self):
        from forkcast.simulation.dynamics import compute_carrying_capacity
        k = compute_carrying_capacity(
            num_agents=20, follower_count=5, hot_topics=["crypto"],
            post_content="Bitcoin is surging", total_agents=20,
        )
        assert k > 0

    def test_hot_topic_multiplier(self):
        from forkcast.simulation.dynamics import compute_carrying_capacity
        k_hot = compute_carrying_capacity(
            num_agents=20, follower_count=5, hot_topics=["crypto"],
            post_content="Crypto is the future", total_agents=20,
        )
        k_cold = compute_carrying_capacity(
            num_agents=20, follower_count=5, hot_topics=["crypto"],
            post_content="The weather is nice", total_agents=20,
        )
        assert k_hot > k_cold

    def test_more_followers_higher_capacity(self):
        from forkcast.simulation.dynamics import compute_carrying_capacity
        k_popular = compute_carrying_capacity(
            num_agents=20, follower_count=15, hot_topics=[],
            post_content="Hello", total_agents=20,
        )
        k_unknown = compute_carrying_capacity(
            num_agents=20, follower_count=1, hot_topics=[],
            post_content="Hello", total_agents=20,
        )
        assert k_popular > k_unknown
