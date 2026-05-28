"""Tests for the optional NextLevel persona-optimizer hook in prepare.py.

The hook is gated on FORKCAST_OPTIMIZE_PERSONAS=1 and soft-imports
forkcast_nextlevel. These tests verify the gate without requiring NextLevel
to be installed and without running the optimizer itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forkcast.simulation.models import AgentProfile
from forkcast.simulation.prepare import _maybe_optimize_personas


def _profile(i: int) -> AgentProfile:
    return AgentProfile(
        agent_id=i,
        name=f"Agent{i}",
        username=f"agent{i}",
        bio=f"bio {i}",
        persona=f"persona {i}",
        age=30,
        gender="n/a",
        profession="tester",
        interests=["a", "b"],
        entity_type="person",
        entity_source="test",
    )


def test_env_var_unset_returns_profiles_unchanged(monkeypatch, tmp_path):
    monkeypatch.delenv("FORKCAST_OPTIMIZE_PERSONAS", raising=False)
    profiles = [_profile(0), _profile(1)]
    result = _maybe_optimize_personas(profiles, tmp_path)
    assert result is profiles  # short-circuit: same object


def test_env_var_set_but_module_missing_returns_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("FORKCAST_OPTIMIZE_PERSONAS", "1")
    # Block the import by inserting a None sentinel into sys.modules.
    monkeypatch.setitem(sys.modules, "forkcast_nextlevel", None)
    monkeypatch.setitem(sys.modules, "forkcast_nextlevel.optimization", None)

    profiles = [_profile(0), _profile(1)]
    result = _maybe_optimize_personas(profiles, tmp_path)
    # Soft-import failed -> caller gets original list, no exception, no file written.
    assert result is profiles
    assert not (tmp_path / "agents.json").exists()


def test_env_var_set_and_module_present_invokes_optimizer(monkeypatch, tmp_path):
    monkeypatch.setenv("FORKCAST_OPTIMIZE_PERSONAS", "1")

    # Build a fake forkcast_nextlevel.optimization module exposing
    # optimize_forkcast_profiles. Profiles are returned with bios reversed so
    # we can assert the hook actually ran.
    fake_pkg = MagicMock()
    fake_opt = MagicMock()

    def fake_optimize(profiles, **kwargs):
        reversed_profiles = list(reversed(profiles))
        stats = {
            "initial_cost": -0.1,
            "final_cost": -0.5,
            "iterations": 100,
            "accepted": 50,
            "improved": True,
        }
        return reversed_profiles, stats

    fake_opt.optimize_forkcast_profiles = fake_optimize
    monkeypatch.setitem(sys.modules, "forkcast_nextlevel", fake_pkg)
    monkeypatch.setitem(sys.modules, "forkcast_nextlevel.optimization", fake_opt)

    profiles = [_profile(0), _profile(1), _profile(2)]
    result = _maybe_optimize_personas(profiles, tmp_path)

    # Hook actually ran — order changed.
    assert [p.agent_id for p in result] == [2, 1, 0]
    # And the agents.json file was rewritten with the optimized set.
    written = json.loads((tmp_path / "agents.json").read_text())
    assert [r["agent_id"] for r in written] == [2, 1, 0]
