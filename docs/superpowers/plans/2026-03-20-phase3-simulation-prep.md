# Phase 3: Simulation Prep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable simulation creation, agent profile generation from knowledge graph entities using Claude extended thinking, and simulation config generation — producing everything needed before a simulation can run.

**Architecture:** Simulation prep is a two-stage pipeline: (1) `sim create` records the simulation in SQLite with engine/platform choices, (2) `sim prepare` reads graph entities, generates agent profiles via Claude extended thinking, generates simulation config via Claude extended thinking, and persists everything to `data/{sim_id}/profiles/agents.json` and `simulations.config_json`. Both stages support SSE progress streaming and are exposed via API + CLI.

**Tech Stack:** Python 3.11, FastAPI, SQLite, Anthropic SDK (extended thinking via `client.think()`), Jinja2 (prompt templating), NetworkX (graph reading), Typer CLI, sse-starlette

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/forkcast/simulation/__init__.py` | Package marker |
| **Create:** `src/forkcast/simulation/models.py` | Dataclasses: `AgentProfile`, `SimulationConfig`, `PrepareResult` |
| **Create:** `src/forkcast/simulation/profile_generator.py` | Generate agent profiles from graph entities using Claude extended thinking, with incremental saving |
| **Create:** `src/forkcast/simulation/config_generator.py` | Generate simulation config using Claude extended thinking |
| **Create:** `src/forkcast/llm/utils.py` | Shared LLM response parsing utilities (code fence stripping) |
| **Create:** `src/forkcast/simulation/prepare.py` | Prepare pipeline orchestrator (profiles → config → persist) with incremental recovery |
| **Create:** `src/forkcast/api/simulation_routes.py` | API routes: create sim, prepare sim, SSE stream, get sim |
| **Create:** `src/forkcast/cli/sim_cmd.py` | CLI commands: sim create, prepare, list, show |
| **Modify:** `src/forkcast/api/app.py:35-43` | Register simulation_router |
| **Modify:** `src/forkcast/cli/__init__.py` | Register sim_app typer subcommand |
| **Create:** `tests/test_simulation_models.py` | Tests for dataclasses and serialization |
| **Create:** `tests/test_profile_generator.py` | Tests for profile generation |
| **Create:** `tests/test_config_generator.py` | Tests for config generation |
| **Create:** `tests/test_prepare_pipeline.py` | Tests for prepare pipeline orchestrator |
| **Create:** `tests/test_api_simulation.py` | Tests for simulation API routes |
| **Create:** `tests/test_cli_sim.py` | Tests for CLI sim commands |

---

### Task 1: Simulation Data Models

**Files:**
- Create: `src/forkcast/simulation/__init__.py`
- Create: `src/forkcast/simulation/models.py`
- Test: `tests/test_simulation_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_models.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/forkcast/simulation/__init__.py
```

```python
# src/forkcast/simulation/models.py
"""Data models for simulation preparation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentProfile:
    """A simulation agent's profile, generated from a knowledge graph entity."""

    agent_id: int
    name: str
    username: str
    bio: str
    persona: str
    age: int
    gender: str
    profession: str
    interests: list[str]
    entity_type: str
    entity_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "username": self.username,
            "bio": self.bio,
            "persona": self.persona,
            "age": self.age,
            "gender": self.gender,
            "profession": self.profession,
            "interests": self.interests,
            "entity_type": self.entity_type,
            "entity_source": self.entity_source,
        }


@dataclass
class SimulationConfig:
    """Generated simulation parameters."""

    total_hours: int
    minutes_per_round: int
    peak_hours: list[int]
    off_peak_hours: list[int]
    peak_multiplier: float
    off_peak_multiplier: float
    seed_posts: list[str]
    hot_topics: list[str]
    narrative_direction: str
    agent_configs: list[dict[str, Any]]
    platform_config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_hours": self.total_hours,
            "minutes_per_round": self.minutes_per_round,
            "peak_hours": self.peak_hours,
            "off_peak_hours": self.off_peak_hours,
            "peak_multiplier": self.peak_multiplier,
            "off_peak_multiplier": self.off_peak_multiplier,
            "seed_posts": self.seed_posts,
            "hot_topics": self.hot_topics,
            "narrative_direction": self.narrative_direction,
            "agent_configs": self.agent_configs,
            "platform_config": self.platform_config,
        }


@dataclass
class PrepareResult:
    """Result of the simulation prepare pipeline."""

    simulation_id: str
    profiles_count: int
    profiles_path: str
    config_generated: bool
    tokens_used: dict[str, int] = field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_models.py -v`
Expected: PASS — all 6 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/__init__.py src/forkcast/simulation/models.py tests/test_simulation_models.py
git commit -m "feat: simulation data models — AgentProfile, SimulationConfig, PrepareResult"
```

---

### Task 2: LLM Utilities + Profile Generator

**Files:**
- Create: `src/forkcast/llm/utils.py`
- Create: `src/forkcast/simulation/profile_generator.py`
- Test: `tests/test_profile_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile_generator.py
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
    client.think.return_value = LLMResponse(
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
        client.think.assert_called_once()


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
        assert client.think.call_count == 1
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_profile_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.llm.utils'`

- [ ] **Step 3: Write LLM utility**

```python
# src/forkcast/llm/utils.py
"""Shared LLM response parsing utilities."""


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM response text."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text
```

- [ ] **Step 4: Write profile generator with incremental saving**

```python
# src/forkcast/simulation/profile_generator.py
"""Generate agent profiles from knowledge graph entities using Claude extended thinking."""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from jinja2 import Template

from forkcast.llm.client import ClaudeClient
from forkcast.llm.utils import strip_code_fences
from forkcast.simulation.models import AgentProfile

logger = logging.getLogger(__name__)


def _build_persona_prompt(
    entity: dict[str, Any],
    related_entities: list[str],
    requirement: str,
    persona_template: str,
) -> str:
    """Build the persona generation prompt using the domain template."""
    template = Template(persona_template)
    return template.render(
        entity_name=entity["name"],
        entity_type=entity["type"],
        entity_description=entity.get("description", ""),
        related_entities=", ".join(related_entities) if related_entities else "None",
        requirement=requirement,
    )


def _get_related_entities(entity_name: str, graph_data: dict[str, Any]) -> list[str]:
    """Find entities connected to the given entity in the graph."""
    related = set()
    for edge in graph_data.get("edges", []):
        if edge["source"] == entity_name:
            related.add(edge["target"])
        elif edge["target"] == entity_name:
            related.add(edge["source"])
    return sorted(related)


def load_existing_profiles(profiles_dir: Path) -> set[str]:
    """Load entity_source names from existing agents.json for incremental recovery."""
    agents_path = profiles_dir / "agents.json"
    if not agents_path.exists():
        return set()
    try:
        data = json.loads(agents_path.read_text(encoding="utf-8"))
        return {p["entity_source"] for p in data if "entity_source" in p}
    except (json.JSONDecodeError, KeyError):
        return set()


def generate_profile(
    client: ClaudeClient,
    entity: dict[str, Any],
    agent_id: int,
    related_entities: list[str],
    requirement: str,
    persona_template: str,
) -> tuple[AgentProfile, dict[str, int]]:
    """Generate a single agent profile using extended thinking.

    Returns (AgentProfile, {"input": N, "output": N}).
    """
    prompt = _build_persona_prompt(
        entity=entity,
        related_entities=related_entities,
        requirement=requirement,
        persona_template=persona_template,
    )

    system = (
        "You are generating a simulation agent profile. "
        "Think deeply about this entity's background, motivations, and communication style. "
        "Return ONLY valid JSON with keys: name, username, bio, persona, age, gender, "
        "profession, interests (array of strings). "
        "No markdown formatting. No code fences."
    )

    response = client.think(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        thinking_budget=8000,
    )

    data = json.loads(strip_code_fences(response.text))

    profile = AgentProfile(
        agent_id=agent_id,
        name=data.get("name", entity["name"]),
        username=data.get("username", entity["name"].lower().replace(" ", "_")),
        bio=data.get("bio", ""),
        persona=data.get("persona", ""),
        age=data.get("age", 30),
        gender=data.get("gender", "unspecified"),
        profession=data.get("profession", ""),
        interests=data.get("interests", []),
        entity_type=entity["type"],
        entity_source=entity["name"],
    )

    tokens = {"input": response.input_tokens, "output": response.output_tokens}
    return profile, tokens


def generate_profiles(
    client: ClaudeClient,
    entities: list[dict[str, Any]],
    graph_data: dict[str, Any],
    requirement: str,
    persona_template: str,
    profiles_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[AgentProfile], dict[str, int]]:
    """Generate profiles for all entities with incremental saving.

    Supports recovery: loads existing profiles from profiles_dir and skips
    entities that already have profiles (matched by entity_source name).

    Returns (all_profiles, {"input": total_in, "output": total_out}).
    """
    existing_sources = load_existing_profiles(profiles_dir)
    profiles: list[AgentProfile] = []
    total_input = 0
    total_output = 0

    # Reload existing profiles as AgentProfile objects
    agents_path = profiles_dir / "agents.json"
    if agents_path.exists():
        try:
            existing_data = json.loads(agents_path.read_text(encoding="utf-8"))
            for pd in existing_data:
                profiles.append(AgentProfile(**pd))
        except (json.JSONDecodeError, TypeError):
            pass

    for i, entity in enumerate(entities):
        if entity["name"] in existing_sources:
            if on_progress:
                on_progress(i + 1, len(entities))
            continue

        related = _get_related_entities(entity["name"], graph_data)
        agent_id = len(profiles)  # Assign next available ID
        profile, tokens = generate_profile(
            client=client,
            entity=entity,
            agent_id=agent_id,
            related_entities=related,
            requirement=requirement,
            persona_template=persona_template,
        )
        profiles.append(profile)
        total_input += tokens["input"]
        total_output += tokens["output"]

        # Incremental save after each profile
        save_profiles(profiles, profiles_dir)

        if on_progress:
            on_progress(i + 1, len(entities))

    return profiles, {"input": total_input, "output": total_output}


def save_profiles(profiles: list[AgentProfile], profiles_dir: Path) -> Path:
    """Save profiles to agents.json. Creates directory if needed."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / "agents.json"
    data = [p.to_dict() for p in profiles]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_profile_generator.py -v`
Expected: PASS — all 10 tests pass

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/llm/utils.py src/forkcast/simulation/profile_generator.py tests/test_profile_generator.py
git commit -m "feat: agent profile generation via Claude extended thinking with incremental save"
```

---

### Task 3: Config Generator

**Files:**
- Create: `src/forkcast/simulation/config_generator.py`
- Test: `tests/test_config_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_generator.py
"""Tests for simulation config generation via Claude extended thinking."""

import json
from unittest.mock import MagicMock

from forkcast.llm.client import LLMResponse
from forkcast.simulation.config_generator import generate_config, _build_config_prompt
from forkcast.simulation.models import AgentProfile, SimulationConfig


def _make_profiles(count=2):
    return [
        AgentProfile(
            agent_id=i, name=f"Agent {i}", username=f"agent{i}", bio=f"Bio {i}",
            persona=f"Persona {i}", age=30 + i, gender="nonbinary",
            profession="Analyst", interests=["data"],
            entity_type="Person", entity_source=f"Entity {i}",
        )
        for i in range(count)
    ]


def _mock_config_response():
    config_json = json.dumps({
        "total_hours": 48,
        "minutes_per_round": 30,
        "peak_hours": [9, 10, 11, 12, 17, 18, 19],
        "off_peak_hours": [0, 1, 2, 3, 4, 5],
        "peak_multiplier": 1.5,
        "off_peak_multiplier": 0.3,
        "seed_posts": ["Breaking news: major policy shift announced"],
        "hot_topics": ["policy", "regulation", "impact"],
        "narrative_direction": "From initial reaction to structured debate",
        "agent_configs": [
            {"agent_id": 0, "activity_level": 0.7, "posts_per_hour": 1.5},
            {"agent_id": 1, "activity_level": 0.5, "posts_per_hour": 1.0},
        ],
        "platform_config": {
            "feed_weights": {"recency": 0.4, "popularity": 0.4, "relevance": 0.2},
            "viral_threshold": 10,
            "echo_chamber_strength": 0.3,
        },
    })
    return LLMResponse(text=config_json, input_tokens=800, output_tokens=600)


class TestBuildConfigPrompt:
    def test_includes_entities_summary(self):
        profiles = _make_profiles(2)
        prompt = _build_config_prompt(
            profiles=profiles,
            requirement="What happens next?",
            config_template="Entities: {{ entities_summary }}\nQuestion: {{ requirement }}",
        )
        assert "Agent 0" in prompt
        assert "Agent 1" in prompt
        assert "What happens next?" in prompt


class TestGenerateConfig:
    def test_generate_config(self):
        client = MagicMock()
        client.think.return_value = _mock_config_response()
        profiles = _make_profiles(2)

        config, tokens = generate_config(
            client=client,
            profiles=profiles,
            requirement="Predict policy impact",
            config_template="Entities: {{ entities_summary }}",
        )

        assert isinstance(config, SimulationConfig)
        assert config.total_hours == 48
        assert config.minutes_per_round == 30
        assert len(config.seed_posts) == 1
        assert len(config.agent_configs) == 2
        assert tokens["input"] == 800
        assert tokens["output"] == 600
        client.think.assert_called_once()

    def test_config_strips_code_fences(self):
        client = MagicMock()
        config_json = json.dumps({
            "total_hours": 24, "minutes_per_round": 15,
            "peak_hours": [10], "off_peak_hours": [2],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": ["post"], "hot_topics": ["topic"],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.think.return_value = LLMResponse(
            text=f"```json\n{config_json}\n```",
            input_tokens=100, output_tokens=50,
        )

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(1),
            requirement="q",
            config_template="t",
        )
        assert config.total_hours == 24

    def test_generate_config_validates_bounds(self):
        client = MagicMock()
        # hours below minimum
        config_json = json.dumps({
            "total_hours": 2, "minutes_per_round": 5,
            "peak_hours": [], "off_peak_hours": [],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": [], "hot_topics": [],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.think.return_value = LLMResponse(
            text=config_json, input_tokens=100, output_tokens=50,
        )

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(1),
            requirement="q",
            config_template="t",
        )
        # Should clamp to spec minimums
        assert config.total_hours >= 12
        assert config.minutes_per_round >= 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_config_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.config_generator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/forkcast/simulation/config_generator.py
"""Generate simulation configuration using Claude extended thinking."""

import json
import logging
from typing import Any

from jinja2 import Template

from forkcast.llm.client import ClaudeClient
from forkcast.llm.utils import strip_code_fences
from forkcast.simulation.models import AgentProfile, SimulationConfig

logger = logging.getLogger(__name__)


def _build_config_prompt(
    profiles: list[AgentProfile],
    requirement: str,
    config_template: str,
) -> str:
    """Build the config generation prompt using the domain template."""
    entities_summary = "\n".join(
        f"- {p.name} ({p.entity_type}): {p.profession}, interests: {', '.join(p.interests)}"
        for p in profiles
    )
    template = Template(config_template)
    return template.render(
        entities_summary=entities_summary,
        requirement=requirement,
    )


def _clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    return max(minimum, min(maximum, value))


def generate_config(
    client: ClaudeClient,
    profiles: list[AgentProfile],
    requirement: str,
    config_template: str,
) -> tuple[SimulationConfig, dict[str, int]]:
    """Generate simulation config using extended thinking.

    Returns (SimulationConfig, {"input": N, "output": N}).
    """
    prompt = _build_config_prompt(
        profiles=profiles,
        requirement=requirement,
        config_template=config_template,
    )

    system = (
        "You are generating simulation parameters for a collective intelligence simulation. "
        "Think carefully about timing, agent behavior, and platform dynamics. "
        "Return ONLY valid JSON matching the requested schema. "
        "No markdown formatting. No code fences."
    )

    response = client.think(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        thinking_budget=10000,
    )

    data = json.loads(strip_code_fences(response.text))

    config = SimulationConfig(
        total_hours=int(_clamp(data.get("total_hours", 48), 12, 168)),
        minutes_per_round=int(_clamp(data.get("minutes_per_round", 30), 15, 60)),
        peak_hours=data.get("peak_hours", [9, 10, 11, 12, 17, 18, 19]),
        off_peak_hours=data.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
        peak_multiplier=float(_clamp(data.get("peak_multiplier", 1.5), 1.0, 3.0)),
        off_peak_multiplier=float(_clamp(data.get("off_peak_multiplier", 0.3), 0.1, 1.0)),
        seed_posts=data.get("seed_posts", []),
        hot_topics=data.get("hot_topics", []),
        narrative_direction=data.get("narrative_direction", ""),
        agent_configs=data.get("agent_configs", []),
        platform_config=data.get("platform_config", {}),
    )

    tokens = {"input": response.input_tokens, "output": response.output_tokens}
    return config, tokens
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_config_generator.py -v`
Expected: PASS — all 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/config_generator.py tests/test_config_generator.py
git commit -m "feat: simulation config generation via Claude extended thinking"
```

---

### Task 4: Prepare Pipeline Orchestrator

**Files:**
- Create: `src/forkcast/simulation/prepare.py`
- Test: `tests/test_prepare_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prepare_pipeline.py
"""Tests for the simulation prepare pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.prepare import prepare_simulation


def _setup_db(db_path: Path, project_id: str = "proj_test1", sim_id: str = "sim_test1"):
    """Create DB with a project, graph, and simulation."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, ?, datetime('now'))",
            (f"graph_{project_id}", project_id, str(db_path.parent / project_id / "graph.json")),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\",\"reddit\"]', datetime('now'))",
            (sim_id, project_id, f"graph_{project_id}"),
        )
    return project_id, sim_id


def _create_graph_file(data_dir: Path, project_id: str):
    """Create a minimal graph.json."""
    graph_dir = data_dir / project_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": [
            {"id": "Dr. Smith", "type": "Researcher", "description": "AI researcher"},
            {"id": "TechCorp", "type": "Organization", "description": "Tech company"},
            {"id": "AI Ethics Board", "type": "Organization", "description": "Ethics org"},
        ],
        "edges": [
            {"source": "Dr. Smith", "target": "TechCorp", "type": "WORKS_AT"},
            {"source": "Dr. Smith", "target": "AI Ethics Board", "type": "MEMBER_OF"},
        ],
    }
    (graph_dir / "graph.json").write_text(json.dumps(graph))
    return graph


def _mock_profile_json():
    return json.dumps({
        "name": "Dr. Smith", "username": "drsmith",
        "bio": "AI researcher", "persona": "A thoughtful researcher...",
        "age": 40, "gender": "female", "profession": "Researcher",
        "interests": ["AI", "ethics"],
    })


def _mock_config_json():
    return json.dumps({
        "total_hours": 48, "minutes_per_round": 30,
        "peak_hours": [10, 11, 12], "off_peak_hours": [2, 3, 4],
        "peak_multiplier": 1.5, "off_peak_multiplier": 0.3,
        "seed_posts": ["Breaking: new policy"], "hot_topics": ["policy"],
        "narrative_direction": "Evolving debate",
        "agent_configs": [{"agent_id": 0, "activity_level": 0.8}],
        "platform_config": {"feed_weights": {"recency": 0.5}},
    })


class TestPreparePipeline:
    def test_prepare_creates_profiles_and_config(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        # Profile generation calls (think) — one per entity
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            # Config generation call (think)
            LLMResponse(text=_mock_config_json(), input_tokens=800, output_tokens=600),
        ]

        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
        )

        assert result.profiles_count == 3
        assert result.config_generated is True
        assert result.tokens_used["input"] > 0
        # Verify profiles file exists
        profiles_path = Path(result.profiles_path)
        assert profiles_path.exists()
        profiles = json.loads(profiles_path.read_text())
        assert len(profiles) == 3

        # Verify config persisted to DB
        with get_db(tmp_db_path) as conn:
            sim = conn.execute(
                "SELECT status, config_json FROM simulations WHERE id = ?", (sim_id,)
            ).fetchone()
        assert sim["status"] == "prepared"
        assert json.loads(sim["config_json"])["total_hours"] == 48

    def test_prepare_not_found(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)
        client = MagicMock()

        with pytest.raises(ValueError, match="Simulation not found"):
            prepare_simulation(
                db_path=tmp_db_path,
                data_dir=tmp_data_dir,
                simulation_id="nonexistent",
                client=client,
                domains_dir=tmp_domains_dir,
            )

    def test_prepare_logs_token_usage(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_config_json(), input_tokens=200, output_tokens=100),
        ]

        prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            usage = conn.execute(
                "SELECT * FROM token_usage WHERE project_id = ? AND stage = 'simulation_prep'",
                (project_id,),
            ).fetchone()
        assert usage is not None
        assert usage["input_tokens"] == 500  # 3*100 + 200
        assert usage["output_tokens"] == 250  # 3*50 + 100

    def test_prepare_progress_callback(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_config_json(), input_tokens=200, output_tokens=100),
        ]

        progress_events = []

        def on_progress(stage, **kwargs):
            progress_events.append({"stage": stage, **kwargs})

        prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
            on_progress=on_progress,
        )

        stages = [e["stage"] for e in progress_events]
        assert "loading_graph" in stages
        assert "generating_profiles" in stages
        assert "generating_config" in stages
        assert "complete" in stages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_prepare_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.prepare'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/forkcast/simulation/prepare.py
"""Orchestrate simulation preparation: profiles + config generation."""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.config_generator import generate_config
from forkcast.simulation.models import PrepareResult
from forkcast.simulation.profile_generator import generate_profiles

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None] | None


def prepare_simulation(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    client: ClaudeClient,
    domains_dir: Path,
    on_progress: ProgressCallback = None,
) -> PrepareResult:
    """Run the full prepare pipeline: load graph → generate profiles → generate config."""

    def _progress(stage: str, **kwargs: Any) -> None:
        if on_progress:
            on_progress(stage=stage, **kwargs)

    # 1. Load simulation and related data
    with get_db(db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        raise ValueError(f"Simulation not found: {simulation_id}")

    project_id = sim["project_id"]
    graph_id = sim["graph_id"]

    with get_db(db_path) as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        graph_row = conn.execute(
            "SELECT * FROM graphs WHERE id = ?", (graph_id,)
        ).fetchone()

    if project is None:
        raise ValueError(f"Project not found: {project_id}")
    if graph_row is None:
        raise ValueError(f"Graph not found: {graph_id}")

    # 2. Load graph data
    _progress("loading_graph")
    graph_path = Path(graph_row["file_path"])
    if not graph_path.exists():
        # Try relative to data_dir
        graph_path = data_dir / project_id / "graph.json"
    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))

    # Extract entities from graph nodes
    entities = []
    for node in graph_data.get("nodes", []):
        entities.append({
            "name": node.get("id", node.get("name", "")),
            "type": node.get("type", "Unknown"),
            "description": node.get("description", ""),
        })

    # 3. Load domain and persona template
    domain = load_domain(project["domain"], domains_dir)
    persona_template = read_prompt(domain, "persona")
    config_template = read_prompt(domain, "config_generation")

    # 4. Generate profiles (with incremental saving for recovery)
    sim_dir = data_dir / simulation_id
    profiles_dir = sim_dir / "profiles"
    _progress("generating_profiles", total=len(entities))
    profiles, profile_tokens = generate_profiles(
        client=client,
        entities=entities,
        graph_data=graph_data,
        requirement=project["requirement"],
        persona_template=persona_template,
        profiles_dir=profiles_dir,
        on_progress=lambda current, total: _progress(
            "generating_profiles", current=current, total=total
        ),
    )
    profiles_path = profiles_dir / "agents.json"

    # 6. Generate config
    _progress("generating_config")
    config, config_tokens = generate_config(
        client=client,
        profiles=profiles,
        requirement=project["requirement"],
        config_template=config_template,
    )

    # 7. Persist config and update simulation status
    config_json = json.dumps(config.to_dict())
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'prepared', config_json = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (config_json, simulation_id),
        )

    # 8. Log token usage
    total_input = profile_tokens["input"] + config_tokens["input"]
    total_output = profile_tokens["output"] + config_tokens["output"]
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO token_usage (project_id, stage, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'simulation_prep', ?, ?, ?, datetime('now'))",
            (project_id, client.default_model, total_input, total_output),
        )

    _progress("complete")

    return PrepareResult(
        simulation_id=simulation_id,
        profiles_count=len(profiles),
        profiles_path=str(profiles_path),
        config_generated=True,
        tokens_used={"input": total_input, "output": total_output},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_prepare_pipeline.py -v`
Expected: PASS — all 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/prepare.py tests/test_prepare_pipeline.py
git commit -m "feat: simulation prepare pipeline — profiles + config generation orchestrator"
```

---

### Task 5: Simulation API Routes

**Files:**
- Create: `src/forkcast/api/simulation_routes.py`
- Modify: `src/forkcast/api/app.py`
- Test: `tests/test_api_simulation.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_simulation.py
"""Tests for simulation API routes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db
from forkcast.simulation.models import PrepareResult


@pytest.fixture
def app_client(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Create test client with initialized DB."""
    init_db(tmp_db_path)

    with patch("forkcast.config.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings

        app = create_app()
        client = TestClient(app)
        yield client, tmp_db_path, tmp_data_dir


def _insert_project_with_graph(db_path: Path, project_id: str = "proj_test1"):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, datetime('now'))",
            (f"graph_{project_id}", project_id),
        )
    return project_id


class TestCreateSimulation:
    def test_create_simulation(self, app_client):
        client, db_path, _ = app_client
        project_id = _insert_project_with_graph(db_path)

        response = client.post("/api/simulations", json={
            "project_id": project_id,
            "engine_type": "oasis",
            "platforms": ["twitter", "reddit"],
        })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["project_id"] == project_id
        assert data["engine_type"] == "oasis"
        assert data["status"] == "created"
        assert "id" in data

    def test_create_simulation_project_not_found(self, app_client):
        client, _, _ = app_client
        response = client.post("/api/simulations", json={
            "project_id": "nonexistent",
            "engine_type": "oasis",
            "platforms": ["twitter"],
        })
        assert response.status_code == 404

    def test_create_simulation_defaults(self, app_client):
        client, db_path, _ = app_client
        project_id = _insert_project_with_graph(db_path)

        response = client.post("/api/simulations", json={
            "project_id": project_id,
        })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["engine_type"] == "oasis"
        assert data["platforms"] == ["twitter", "reddit"]


class TestGetSimulation:
    def test_get_simulation(self, app_client):
        client, db_path, _ = app_client
        project_id = _insert_project_with_graph(db_path)

        # Create sim via API
        create_resp = client.post("/api/simulations", json={"project_id": project_id})
        sim_id = create_resp.json()["data"]["id"]

        response = client.get(f"/api/simulations/{sim_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == sim_id
        assert data["status"] == "created"

    def test_get_simulation_not_found(self, app_client):
        client, _, _ = app_client
        response = client.get("/api/simulations/nonexistent")
        assert response.status_code == 404


class TestTriggerPrepare:
    def test_trigger_prepare_returns_immediately(self, app_client):
        """POST /prepare should return immediately with status 'preparing'."""
        client, db_path, _ = app_client
        project_id = _insert_project_with_graph(db_path)
        create_resp = client.post("/api/simulations", json={"project_id": project_id})
        sim_id = create_resp.json()["data"]["id"]

        with patch("forkcast.api.simulation_routes.ClaudeClient"):
            with patch("forkcast.api.simulation_routes.prepare_simulation"):
                response = client.post(f"/api/simulations/{sim_id}/prepare")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "preparing"
        assert data["simulation_id"] == sim_id

    def test_trigger_prepare_not_found(self, app_client):
        client, _, _ = app_client
        response = client.post("/api/simulations/nonexistent/prepare")
        assert response.status_code == 404


class TestListSimulations:
    def test_list_simulations(self, app_client):
        client, db_path, _ = app_client
        project_id = _insert_project_with_graph(db_path)
        client.post("/api/simulations", json={"project_id": project_id})

        response = client.get("/api/simulations")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_simulation.py -v`
Expected: FAIL — `ModuleNotFoundError` or route not found (404)

- [ ] **Step 3: Write simulation routes**

```python
# src/forkcast/api/simulation_routes.py
"""Simulation management API routes with SSE streaming."""

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.prepare import prepare_simulation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# Per-simulation progress queues. Created on POST /prepare, consumed by GET /prepare/stream.
_prepare_queues: dict[str, asyncio.Queue] = {}


class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str = "oasis"
    platforms: list[str] = ["twitter", "reddit"]


@router.post("")
async def create_simulation(req: CreateSimulationRequest):
    """Create a new simulation for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (req.project_id,)
        ).fetchone()

    if project is None:
        return error(f"Project not found: {req.project_id}", status_code=404)

    # Find the latest graph for this project
    with get_db(settings.db_path) as conn:
        graph = conn.execute(
            "SELECT id FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (req.project_id,),
        ).fetchone()

    graph_id = graph["id"] if graph else None

    sim_id = f"sim_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?)",
            (sim_id, req.project_id, graph_id, req.engine_type, json.dumps(req.platforms), now),
        )

    return success(
        {
            "id": sim_id,
            "project_id": req.project_id,
            "graph_id": graph_id,
            "status": "created",
            "engine_type": req.engine_type,
            "platforms": req.platforms,
            "created_at": now,
        },
        status_code=201,
    )


@router.get("")
async def list_simulations():
    """List all simulations."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, project_id, graph_id, status, engine_type, platforms, created_at, updated_at "
            "FROM simulations ORDER BY created_at DESC"
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["platforms"] = json.loads(d["platforms"]) if d["platforms"] else []
        results.append(d)

    return success(results)


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    """Get simulation details."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    d = dict(sim)
    d["platforms"] = json.loads(d["platforms"]) if d["platforms"] else []
    if d.get("config_json"):
        d["config"] = json.loads(d["config_json"])
    d.pop("config_json", None)
    return success(d)


@router.post("/{simulation_id}/prepare")
async def trigger_prepare(simulation_id: str):
    """Trigger simulation preparation as a background task.

    Returns immediately with status 'preparing'. Monitor progress via
    GET /api/simulations/{id}/prepare/stream (SSE).
    """
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    # Create a queue for this simulation's progress events
    queue: asyncio.Queue = asyncio.Queue()
    _prepare_queues[simulation_id] = queue
    loop = asyncio.get_event_loop()

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        # Thread-safe: put_nowait from worker thread via call_soon_threadsafe
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _run_prepare():
        return prepare_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )

    async def _background_prepare():
        try:
            result = await asyncio.to_thread(_run_prepare)
            queue.put_nowait({
                "stage": "result",
                "simulation_id": result.simulation_id,
                "profiles_count": result.profiles_count,
                "config_generated": result.config_generated,
                "tokens_used": result.tokens_used,
            })
        except Exception as e:
            logger.exception(f"Simulation prepare failed for {simulation_id}")
            queue.put_nowait({"stage": "error", "message": str(e)})
        finally:
            queue.put_nowait(None)  # Sentinel to close SSE stream

    # Fire and forget — client monitors via SSE stream
    asyncio.create_task(_background_prepare())

    return success({"status": "preparing", "simulation_id": simulation_id})


@router.get("/{simulation_id}/prepare/stream")
async def stream_prepare(simulation_id: str, request: Request):
    """SSE stream for simulation preparation progress."""
    queue = _prepare_queues.get(simulation_id)
    if queue is None:
        return error("No prepare job running for this simulation", status_code=404)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                _prepare_queues.pop(simulation_id, None)
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Register simulation router in app.py**

Add to `src/forkcast/api/app.py` after the graph router:

```python
    from forkcast.api.simulation_routes import router as simulation_router
    app.include_router(simulation_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_simulation.py -v`
Expected: PASS — all 8 tests pass

- [ ] **Step 6: Run all tests**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests pass (existing + new)

- [ ] **Step 7: Commit**

```bash
git add src/forkcast/api/simulation_routes.py src/forkcast/api/app.py tests/test_api_simulation.py
git commit -m "feat: simulation API routes — create, prepare, SSE stream, get, list"
```

---

### Task 6: CLI Simulation Commands

**Files:**
- Create: `src/forkcast/cli/sim_cmd.py`
- Modify: `src/forkcast/cli/__init__.py` (register sim_app)
- Test: `tests/test_cli_sim.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_sim.py
"""Tests for CLI simulation commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.sim_cmd import sim_app
from forkcast.db.connection import get_db, init_db
from forkcast.simulation.models import PrepareResult


runner = CliRunner()


def _setup_db(db_path, data_dir):
    """Create DB with project and graph."""
    init_db(db_path)
    project_id = "proj_test1"
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, ?, datetime('now'))",
            (f"graph_{project_id}", project_id, str(data_dir / project_id / "graph.json")),
        )

    # Create graph file
    graph_dir = data_dir / project_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "Entity1", "type": "Person", "description": "desc"}],
        "edges": [],
    }))

    return project_id


class TestSimCreate:
    def test_create_simulation(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            settings.domains_dir = tmp_domains_dir
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["create", project_id])

        assert result.exit_code == 0
        assert "Simulation created" in result.output
        assert "sim_" in result.output

    def test_create_simulation_project_not_found(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["create", "nonexistent"])

        assert result.exit_code == 1


class TestSimPrepare:
    def test_prepare_simulation(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)

        # Create a simulation in DB
        sim_id = "sim_test123"
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\"]', datetime('now'))",
                (sim_id, project_id, f"graph_{project_id}"),
            )

        mock_result = PrepareResult(
            simulation_id=sim_id,
            profiles_count=5,
            profiles_path=str(tmp_data_dir / sim_id / "profiles" / "agents.json"),
            config_generated=True,
            tokens_used={"input": 1000, "output": 500},
        )

        with (
            patch("forkcast.cli.sim_cmd.get_settings") as mock_settings,
            patch("forkcast.cli.sim_cmd.prepare_simulation", return_value=mock_result) as mock_prepare,
            patch("forkcast.cli.sim_cmd.ClaudeClient"),
        ):
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            settings.domains_dir = tmp_domains_dir
            settings.anthropic_api_key = "test-key"
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["prepare", sim_id])

        assert result.exit_code == 0
        assert "Profiles: 5" in result.output or "profiles_count" in result.output.lower() or "5" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_sim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.cli.sim_cmd'`

- [ ] **Step 3: Write CLI commands**

```python
# src/forkcast/cli/sim_cmd.py
"""CLI commands for simulation management."""

import json
import secrets
from datetime import datetime, timezone
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.prepare import prepare_simulation

sim_app = typer.Typer(help="Manage simulations", no_args_is_help=True)


@sim_app.command("create")
def sim_create(
    project_id: str,
    engine: Annotated[str, typer.Option(help="Simulation engine")] = "oasis",
    platforms: Annotated[str, typer.Option(help="Comma-separated platforms")] = "twitter,reddit",
):
    """Create a new simulation for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    if project is None:
        typer.echo(f"Error: Project not found: {project_id}", err=True)
        raise typer.Exit(code=1)

    # Find latest graph
    with get_db(settings.db_path) as conn:
        graph = conn.execute(
            "SELECT id FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    graph_id = graph["id"] if graph else None
    platform_list = [p.strip() for p in platforms.split(",")]
    sim_id = f"sim_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?)",
            (sim_id, project_id, graph_id, engine, json.dumps(platform_list), now),
        )

    typer.echo(f"Simulation created: {sim_id}")
    typer.echo(f"  Project:   {project_id}")
    typer.echo(f"  Engine:    {engine}")
    typer.echo(f"  Platforms: {', '.join(platform_list)}")
    if graph_id:
        typer.echo(f"  Graph:     {graph_id}")


@sim_app.command("prepare")
def sim_prepare(simulation_id: str):
    """Prepare a simulation (generate profiles + config)."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        typer.echo(f"Error: Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Preparing simulation {simulation_id}...")
    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        current = kwargs.get("current", "")
        total = kwargs.get("total", "")
        if current and total:
            typer.echo(f"  [{stage}] {current}/{total}")
        else:
            typer.echo(f"  [{stage}]")

    try:
        result = prepare_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nSimulation prepared!")
    typer.echo(f"  Profiles: {result.profiles_count}")
    typer.echo(f"  Config:   {'generated' if result.config_generated else 'failed'}")
    typer.echo(f"  Tokens:   {result.tokens_used.get('input', 0)} in / {result.tokens_used.get('output', 0)} out")


@sim_app.command("list")
def sim_list():
    """List all simulations."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, project_id, status, engine_type, platforms, created_at "
            "FROM simulations ORDER BY created_at DESC"
        ).fetchall()

    if not rows:
        typer.echo("No simulations found.")
        return

    typer.echo(f"{'ID':<20} {'Project':<20} {'Status':<12} {'Engine':<10} {'Created'}")
    typer.echo("-" * 90)
    for row in rows:
        typer.echo(
            f"{row['id']:<20} {row['project_id']:<20} {row['status']:<12} "
            f"{row['engine_type']:<10} {row['created_at']}"
        )


@sim_app.command("show")
def sim_show(simulation_id: str):
    """Show simulation details."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        typer.echo(f"Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    platforms = json.loads(sim["platforms"]) if sim["platforms"] else []
    typer.echo(f"ID:        {sim['id']}")
    typer.echo(f"Project:   {sim['project_id']}")
    typer.echo(f"Graph:     {sim['graph_id'] or 'none'}")
    typer.echo(f"Status:    {sim['status']}")
    typer.echo(f"Engine:    {sim['engine_type']}")
    typer.echo(f"Platforms: {', '.join(platforms)}")
    typer.echo(f"Created:   {sim['created_at']}")
    if sim["config_json"]:
        config = json.loads(sim["config_json"])
        typer.echo(f"\nConfig:")
        typer.echo(f"  Duration:  {config.get('total_hours', '?')}h")
        typer.echo(f"  Round:     {config.get('minutes_per_round', '?')}min")
        typer.echo(f"  Topics:    {', '.join(config.get('hot_topics', []))}")
```

- [ ] **Step 4: Register sim_app in CLI**

Read `src/forkcast/cli/__init__.py` (currently nearly empty). Update the main CLI entry point to register `sim_app`. The main CLI is at `src/forkcast/cli/main.py` — check for typer app registration there.

Find where `project_app` is registered and add `sim_app` similarly:

```python
from forkcast.cli.sim_cmd import sim_app
app.add_typer(sim_app, name="sim")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_sim.py -v`
Expected: PASS — all 3 tests pass

- [ ] **Step 6: Run all tests**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/forkcast/cli/sim_cmd.py src/forkcast/cli/main.py src/forkcast/api/app.py tests/test_cli_sim.py
git commit -m "feat: CLI sim commands — create, prepare, list, show"
```

---

### Task 7: Integration Test — Full Prepare Pipeline

**Files:**
- Test: `tests/test_integration_prepare.py`

This task verifies the full end-to-end flow: create simulation via API → prepare via pipeline → verify profiles file + config in DB + token usage logged.

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration_prepare.py
"""Integration test: full simulation create + prepare flow."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse


def _mock_profile():
    return json.dumps({
        "name": "Agent X", "username": "agentx",
        "bio": "Test agent", "persona": "A test persona",
        "age": 30, "gender": "other", "profession": "Tester",
        "interests": ["testing"],
    })


def _mock_config():
    return json.dumps({
        "total_hours": 24, "minutes_per_round": 15,
        "peak_hours": [10, 11], "off_peak_hours": [2, 3],
        "peak_multiplier": 1.2, "off_peak_multiplier": 0.5,
        "seed_posts": ["Test post"], "hot_topics": ["testing"],
        "narrative_direction": "Test direction",
        "agent_configs": [{"agent_id": 0, "activity_level": 0.5}],
        "platform_config": {"feed_weights": {"recency": 0.5}},
    })


class TestFullPrepareFlow:
    def test_create_sim_then_prepare_pipeline(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        """Integration test: create sim via API, then run prepare pipeline directly."""
        init_db(tmp_db_path)
        project_id = "proj_integ"

        # Setup: project + graph + graph file
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, '_default', 'Integration', 'graph_built', 'Test prediction', datetime('now'))",
                (project_id,),
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
                "VALUES (?, ?, 'complete', 2, 1, ?, datetime('now'))",
                (f"graph_{project_id}", project_id, str(tmp_data_dir / project_id / "graph.json")),
            )

        graph_dir = tmp_data_dir / project_id
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / "graph.json").write_text(json.dumps({
            "nodes": [
                {"id": "Alice", "type": "Person", "description": "Engineer"},
                {"id": "Bob", "type": "Person", "description": "Manager"},
            ],
            "edges": [
                {"source": "Alice", "target": "Bob", "type": "REPORTS_TO"},
            ],
        }))

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.think.side_effect = [
            LLMResponse(text=_mock_profile(), input_tokens=200, output_tokens=100),
            LLMResponse(text=_mock_profile(), input_tokens=200, output_tokens=100),
            LLMResponse(text=_mock_config(), input_tokens=400, output_tokens=200),
        ]

        with patch("forkcast.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            settings.domains_dir = tmp_domains_dir
            settings.anthropic_api_key = "test-key"
            mock_settings.return_value = settings

            app = create_app()
            client = TestClient(app)

            # Step 1: Create simulation via API
            create_resp = client.post("/api/simulations", json={
                "project_id": project_id,
                "engine_type": "claude",
                "platforms": ["twitter"],
            })
            assert create_resp.status_code == 201
            sim_id = create_resp.json()["data"]["id"]

        # Step 2: Run prepare pipeline directly (the API fires this as background task)
        from forkcast.simulation.prepare import prepare_simulation
        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert result.profiles_count == 2
        assert result.config_generated is True

        # Verify: profiles file exists
        profiles_path = tmp_data_dir / sim_id / "profiles" / "agents.json"
        assert profiles_path.exists()
        profiles = json.loads(profiles_path.read_text())
        assert len(profiles) == 2

        # Verify: simulation status updated
        with get_db(tmp_db_path) as conn:
            sim = conn.execute(
                "SELECT status, config_json FROM simulations WHERE id = ?", (sim_id,)
            ).fetchone()
        assert sim["status"] == "prepared"
        config = json.loads(sim["config_json"])
        assert config["total_hours"] == 24

        # Verify: token usage logged
        with get_db(tmp_db_path) as conn:
            usage = conn.execute(
                "SELECT * FROM token_usage WHERE project_id = ? AND stage = 'simulation_prep'",
                (project_id,),
            ).fetchone()
        assert usage is not None
        assert usage["input_tokens"] == 800  # 2*200 + 400
        assert usage["output_tokens"] == 400  # 2*100 + 200
```

- [ ] **Step 2: Run integration test**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_integration_prepare.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_prepare.py
git commit -m "test: integration test for full simulation create + prepare flow"
```

---

## Summary

| Task | What It Builds | New Tests |
|------|---------------|-----------|
| 1 | `AgentProfile`, `SimulationConfig`, `PrepareResult` dataclasses | 6 |
| 2 | LLM utils (`strip_code_fences`) + Profile generator with incremental save & recovery | 10 |
| 3 | Config generator (Claude extended thinking + bounds validation) | 4 |
| 4 | Prepare pipeline orchestrator (graph → profiles → config → DB) | 4 |
| 5 | API routes: create, prepare (non-blocking), get, list, SSE stream | 8 |
| 6 | CLI: sim create, prepare, list, show | 3 |
| 7 | Integration test: full create → prepare flow | 1 |
| **Total** | | **~36 new tests** |

### Design Decisions

- **POST /prepare is non-blocking**: Returns immediately with `{"status": "preparing"}`. Background task runs via `asyncio.create_task`. Progress monitored via SSE at `GET /prepare/stream`.
- **Thread-safe queue**: `loop.call_soon_threadsafe(queue.put_nowait, event)` for progress events from `asyncio.to_thread` worker.
- **Incremental profile saving**: Each profile is saved to `agents.json` as it completes. On restart, `load_existing_profiles()` skips entities that already have profiles (matched by `entity_source` name).
- **Shared `strip_code_fences` utility**: Extracted to `src/forkcast/llm/utils.py` — used by both profile and config generators.
- **CLI calls pipeline directly**: The CLI calls `prepare_simulation()` directly rather than consuming the SSE API. This is an acceptable simplification for Phase 3 — the API pattern is for web clients.

**After Phase 3:** `forkcast sim create <project_id>` + `forkcast sim prepare <sim_id>` work end-to-end, generating agent profiles and simulation configuration from the knowledge graph using Claude extended thinking.
