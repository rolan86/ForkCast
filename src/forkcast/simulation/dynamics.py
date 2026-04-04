"""Dynamics helpers — carrying capacity computation and extension hooks.

Re-exports ODE classes from forkcast-nextlevel when available. The runner
and engine import from this module so they never need to know whether the
proprietary package is installed.
"""

# Re-export proprietary dynamics classes (graceful degradation)
try:
    from forkcast_nextlevel.simulation.dynamics import (  # noqa: F401
        CircadianModel,
        DynamicsState,
        EngagementModel,
        EulerIntegrator,
        Integrator,
        RKIntegrator,
        AdaptiveOrderIntegrator,
        create_integrator,
        compute_phase_offset,
    )

    HAS_DYNAMICS = True
except ImportError:
    HAS_DYNAMICS = False


def compute_carrying_capacity(
    num_agents: int,
    follower_count: int,
    hot_topics: list[str],
    post_content: str,
    total_agents: int,
) -> float:
    """Compute carrying capacity K for a post's engagement model.

    K = base_engagement * (1 + follower_ratio) * topic_multiplier
    """
    base_engagement = max(1.0, num_agents * 0.5)
    follower_ratio = follower_count / max(1, total_agents)
    # Case-insensitive substring match for hot topics
    content_lower = post_content.lower()
    topic_multiplier = 2.0 if any(t.lower() in content_lower for t in hot_topics) else 1.0
    return base_engagement * (1.0 + follower_ratio) * topic_multiplier
