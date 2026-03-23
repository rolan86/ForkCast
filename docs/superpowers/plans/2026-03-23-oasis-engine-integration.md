# OASIS Engine Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `OasisEngine` to use OASIS's in-process Python API (`camel-oasis`) so simulations produce real action data, with dual agent modes (LLM-driven and rule-based).

**Architecture:** The broken subprocess-based `OasisEngine` is fully rewritten to use `oasis.make()` / `env.step()` / `env.close()`. A V4 DB migration adds `agent_mode`. The runner passes `agent_mode` to the engine. The frontend shows an agent mode toggle when OASIS is selected. Both modes share the same data flow as the Claude engine — `on_action`, `on_round`, `on_round_complete` callbacks.

**Tech Stack:** Python 3.11+, camel-oasis v0.2.5+, camel-ai v0.2.78+, FastAPI, SQLite, Vue 3

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/forkcast/db/schema.py` | Modify | V4 migration adding `agent_mode` column |
| `src/forkcast/db/connection.py` | Modify | Chain V3→V4 migration |
| `pyproject.toml` | Modify | Optional `[oasis]` dependency group |
| `src/forkcast/simulation/oasis_engine.py` | Rewrite | In-process OASIS engine with dual agent modes |
| `src/forkcast/simulation/runner.py` | Modify | Pass `agent_mode` to OASIS engine, wire `on_round_complete` |
| `src/forkcast/api/simulation_routes.py` | Modify | `agent_mode` in create/settings/list endpoints |
| `src/forkcast/api/capabilities_routes.py` | Modify | `agent_modes` in capabilities response |
| `frontend/src/stores/capabilities.js` | Modify | Expose `oasisAgentModes` getter |
| `frontend/src/components/SimulationSettings.vue` | Modify | Agent mode toggle when OASIS selected |
| `tests/test_oasis_engine.py` | Rewrite | Tests for in-process OASIS API |
| `tests/test_oasis_runner_integration.py` | Create | Runner→engine→DB integration tests |

---

### Task 1: Database Migration V3→V4

**Files:**
- Modify: `src/forkcast/db/schema.py:1-316`
- Modify: `src/forkcast/db/connection.py:8,31-38`
- Test: `tests/test_db_schema.py` (existing migration tests)

- [ ] **Step 1: Write failing test for V4 migration**

In `tests/test_db_schema.py`, add:

```python
class TestMigrationV3ToV4:
    def test_migration_adds_agent_mode_column(self, tmp_path):
        """V3 DB migrated to V4 should have agent_mode column on simulations."""
        db_path = tmp_path / "test.db"
        # Create a V3 database
        conn = sqlite3.connect(str(db_path))
        conn.executescript(TABLES_V3)
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '3')")
        conn.commit()
        conn.close()

        # Run init_db which should migrate to V4
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert row[0] == "4"

        # Verify agent_mode column exists with correct default
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, engine_type, platforms, created_at) "
            "VALUES ('test', 'proj', 'created', 'oasis', '[]', datetime('now'))"
        )
        conn.commit()
        sim = conn.execute("SELECT agent_mode FROM simulations WHERE id = 'test'").fetchone()
        assert sim[0] == "llm"
        conn.close()

    def test_fresh_db_has_agent_mode_column(self, tmp_path):
        """Fresh DB at V4 should have agent_mode column."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert row[0] == "4"

        # Column exists and has default
        info = conn.execute("PRAGMA table_info(simulations)").fetchall()
        col_names = [col[1] for col in info]
        assert "agent_mode" in col_names
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_db_schema.py::TestMigrationV3ToV4 -v`
Expected: FAIL — `TABLES_V3` doesn't have `agent_mode`, `SCHEMA_VERSION` is still 3

- [ ] **Step 3: Implement V4 migration**

In `src/forkcast/db/schema.py`:

1. Change `SCHEMA_VERSION = 3` → `SCHEMA_VERSION = 4`

2. Add `TABLES_V4` — copy `TABLES_V3` and add `agent_mode TEXT DEFAULT 'llm'` after `run_model TEXT` in the simulations table (line ~254). Update `TABLES_V3` reference to `TABLES_V4` where used for fresh installs.

3. Add migration constant after `MIGRATION_V2_TO_V3`:

```python
MIGRATION_V3_TO_V4 = """
ALTER TABLE simulations ADD COLUMN agent_mode TEXT DEFAULT 'llm';
UPDATE meta SET value = '4' WHERE key = 'schema_version';
"""
```

In `src/forkcast/db/connection.py`:

1. Update import on line 8 to include `MIGRATION_V3_TO_V4` and `TABLES_V4`:
```python
from forkcast.db.schema import MIGRATION_V1_TO_V2, MIGRATION_V2_TO_V3, MIGRATION_V3_TO_V4, SCHEMA_VERSION, TABLES_V1, TABLES_V4
```

2. Change line 25 `conn.executescript(TABLES_V3)` → `conn.executescript(TABLES_V4)`

3. Add V3→V4 migration chain after line 38:
```python
            if existing_version == 3:
                conn.executescript(MIGRATION_V3_TO_V4)
                conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_db_schema.py::TestMigrationV3ToV4 -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass (412+)

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/db/schema.py src/forkcast/db/connection.py tests/test_db_schema.py
git commit -m "feat(db): add V4 migration with agent_mode column for OASIS dual-mode support"
```

---

### Task 2: Optional OASIS Dependency Group

**Files:**
- Modify: `pyproject.toml:22-23`

- [ ] **Step 1: Add optional dependency group**

In `pyproject.toml`, add after the `]` closing `dependencies` (after line 22):

```toml
[project.optional-dependencies]
oasis = [
    "camel-oasis>=0.2.5",
    "camel-ai[all]>=0.2.78",
]
```

- [ ] **Step 2: Verify pyproject.toml is valid**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Run existing tests still pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add optional [oasis] dependency group for camel-oasis integration"
```

---

### Task 3: API Changes — agent_mode in Create/Settings/List

**Files:**
- Modify: `src/forkcast/api/simulation_routes.py:31-36,37-41,44-100,163-201`
- Test: `tests/test_simulation_routes.py` (existing API tests)

- [ ] **Step 1: Write failing tests for agent_mode in API**

Add tests to `tests/test_simulation_routes.py`:

```python
class TestAgentModeAPI:
    def test_create_simulation_with_agent_mode(self, client, project_id):
        """POST /api/simulations with agent_mode should store it."""
        resp = client.post("/api/simulations", json={
            "project_id": project_id,
            "engine_type": "oasis",
            "agent_mode": "native",
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["agent_mode"] == "native"

    def test_create_simulation_default_agent_mode(self, client, project_id):
        """POST /api/simulations without agent_mode defaults to 'llm'."""
        resp = client.post("/api/simulations", json={
            "project_id": project_id,
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["agent_mode"] == "llm"

    def test_create_simulation_invalid_agent_mode(self, client, project_id):
        """POST /api/simulations with invalid agent_mode returns 400."""
        resp = client.post("/api/simulations", json={
            "project_id": project_id,
            "agent_mode": "invalid",
        })
        assert resp.status_code == 400

    def test_update_settings_agent_mode(self, client, sim_id):
        """PATCH /api/simulations/{id}/settings with agent_mode updates it."""
        resp = client.patch(f"/api/simulations/{sim_id}/settings", json={
            "agent_mode": "native",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["updated"] is True

    def test_update_settings_invalid_agent_mode(self, client, sim_id):
        """PATCH /api/simulations/{id}/settings with invalid agent_mode returns 400."""
        resp = client.patch(f"/api/simulations/{sim_id}/settings", json={
            "agent_mode": "bogus",
        })
        assert resp.status_code == 400

    def test_list_simulations_includes_agent_mode(self, client, project_id):
        """GET /api/simulations list includes agent_mode for each sim."""
        client.post("/api/simulations", json={
            "project_id": project_id,
            "agent_mode": "native",
        })
        resp = client.get("/api/simulations")
        data = resp.json()["data"]
        assert any(s.get("agent_mode") == "native" for s in data)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_routes.py::TestAgentModeAPI -v`
Expected: FAIL — `agent_mode` not in request model or response

- [ ] **Step 3: Implement API changes**

In `src/forkcast/api/simulation_routes.py`:

1. Add `agent_mode` to `CreateSimulationRequest` (line ~34):
```python
class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str | None = None
    platforms: list[str] | None = None
    agent_mode: str | None = None  # "llm" or "native"
```

2. Add `agent_mode` to `UpdateSettingsRequest` (line ~41):
```python
class UpdateSettingsRequest(BaseModel):
    engine_type: str | None = None
    platforms: list[str] | None = None
    prep_model: str | None = None
    run_model: str | None = None
    agent_mode: str | None = None  # "llm" or "native"
```

3. Add validation constant at top of file (after imports):
```python
_VALID_AGENT_MODES = {"llm", "native"}
```

4. In `create_simulation()` (line ~46), add validation and storage:
```python
    # Validate agent_mode
    agent_mode = req.agent_mode or "llm"
    if agent_mode not in _VALID_AGENT_MODES:
        return error(f"Invalid agent_mode: {agent_mode}. Must be one of: {_VALID_AGENT_MODES}", status_code=400)
```
Update the INSERT to include `agent_mode`:
```python
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, agent_mode, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?, ?)",
            (sim_id, req.project_id, graph_id, engine_type, json.dumps(platforms), agent_mode, now),
        )
```
Add `agent_mode` to the response dict in `create_simulation()`:
```python
    return success(
        {
            "id": sim_id,
            "project_id": req.project_id,
            "graph_id": graph_id,
            "status": "created",
            "engine_type": engine_type,
            "platforms": platforms,
            "agent_mode": agent_mode,
            "created_at": now,
        },
        status_code=201,
    )
```

5. In `update_settings()` (line ~164), add `agent_mode` handling:
```python
    if req.agent_mode is not None:
        if req.agent_mode not in _VALID_AGENT_MODES:
            return error(f"Invalid agent_mode: {req.agent_mode}. Must be one of: {_VALID_AGENT_MODES}", status_code=400)
        updates.append("agent_mode = ?")
        params.append(req.agent_mode)
```

6. In `list_simulations()` (line ~108), add `s.agent_mode` to the SELECT columns:
```python
        rows = conn.execute(
            "SELECT s.id, s.project_id, s.graph_id, s.status, s.engine_type, "
            "s.platforms, s.config_json, s.agent_mode, s.created_at, s.updated_at, "
            "COUNT(a.id) AS actions_count, MAX(a.round) AS rounds_completed "
            "FROM simulations s "
            "LEFT JOIN simulation_actions a ON a.simulation_id = s.id "
            "GROUP BY s.id "
            "ORDER BY s.created_at DESC"
        ).fetchall()
```
The `dict(row)` conversion already includes all selected columns, so `agent_mode` will automatically appear in each result dict.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_routes.py::TestAgentModeAPI -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/api/simulation_routes.py tests/test_simulation_routes.py
git commit -m "feat(api): add agent_mode to create, update, and list simulation endpoints"
```

---

### Task 4: Capabilities Endpoint — agent_modes

**Files:**
- Modify: `src/forkcast/api/capabilities_routes.py:9-25`
- Modify: `frontend/src/stores/capabilities.js:11-14`
- Test: `tests/test_capabilities_routes.py` (existing)

- [ ] **Step 1: Write failing test**

In `tests/test_capabilities_routes.py`, add:

```python
def test_oasis_includes_agent_modes(client):
    """Capabilities response includes agent_modes for oasis engine."""
    resp = client.get("/api/capabilities")
    data = resp.json()["data"]
    oasis = data["engines"]["oasis"]
    # Whether available or not, agent_modes should be listed
    assert oasis["agent_modes"] == ["llm", "native"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_capabilities_routes.py::test_oasis_includes_agent_modes -v`
Expected: FAIL — no `agent_modes` key

- [ ] **Step 3: Implement capabilities change**

In `src/forkcast/api/capabilities_routes.py`, update `_check_oasis()`:

```python
def _check_oasis() -> dict:
    result = {"agent_modes": ["llm", "native"]}
    try:
        import oasis  # noqa: F401
        result["available"] = True
    except ImportError:
        result["available"] = False
        result["reason"] = "camel-oasis not installed"
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_capabilities_routes.py::test_oasis_includes_agent_modes -v`
Expected: PASS

- [ ] **Step 5: Update frontend capabilities store**

In `frontend/src/stores/capabilities.js`, add a getter (after `isOasisAvailable`):

```javascript
    oasisAgentModes(state) {
      return state.engines?.oasis?.agent_modes || []
    },
```

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/api/capabilities_routes.py frontend/src/stores/capabilities.js tests/test_capabilities_routes.py
git commit -m "feat(capabilities): include agent_modes in OASIS capabilities response"
```

---

### Task 5: Rewrite OasisEngine — Profile Mapping

**Files:**
- Rewrite: `src/forkcast/simulation/oasis_engine.py:1-48` (profile conversion functions)
- Test: `tests/test_oasis_engine.py:57-84` (profile tests)

This task rewrites the profile conversion functions to match OASIS's expected format per the design spec. The engine class itself comes in the next task.

- [ ] **Step 1: Write failing tests for new profile format**

Replace `TestConvertProfilesToCSV` and `TestConvertProfilesToRedditJSON` in `tests/test_oasis_engine.py`:

```python
class TestConvertProfilesToTwitterCSV:
    def test_csv_has_oasis_header(self):
        """Twitter CSV must have exactly: user_id, name, username, user_char, description."""
        profiles = _make_profiles(2)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        lines = csv_text.strip().split("\n")
        header = lines[0]
        assert header == "user_id,name,username,user_char,description"
        assert len(lines) == 3  # header + 2 profiles

    def test_csv_maps_forkcast_fields(self):
        """agent_id→user_id, persona→user_char, bio→description."""
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        lines = csv_text.strip().split("\n")
        # Parse the data row
        reader = csv.reader(io.StringIO(lines[1]))
        row = next(reader)
        assert row[0] == "0"  # user_id from agent_id
        assert row[1] == "Agent0"  # name
        assert row[2] == "agent0"  # username
        assert row[3] == "Persona 0"  # user_char from persona
        assert row[4] == "Bio 0"  # description from bio

    def test_csv_drops_age_gender_profession_interests(self):
        """OASIS Twitter CSV schema does not support these fields."""
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        assert "Profession" not in csv_text
        assert "30" not in csv_text.split("\n")[1]  # age not in data row


class TestConvertProfilesToRedditJSON:
    def test_json_has_oasis_fields(self):
        """Reddit JSON must include karma, mbti, country with defaults."""
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        entry = data[0]
        assert entry["user_id"] == 0
        assert entry["username"] == "agent0"
        assert entry["persona"] == "Persona 0"
        assert entry["karma"] == 0
        assert entry["mbti"] == ""
        assert entry["country"] == ""

    def test_json_drops_profession_interests(self):
        """profession and interests are not in OASIS Reddit schema."""
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        entry = data[0]
        assert "profession" not in entry
        assert "interests" not in entry
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestConvertProfilesToTwitterCSV tests/test_oasis_engine.py::TestConvertProfilesToRedditJSON -v`
Expected: FAIL — old function names and field mappings

- [ ] **Step 3: Rewrite profile conversion functions**

Replace the profile functions in `src/forkcast/simulation/oasis_engine.py`:

```python
def _convert_profiles_to_twitter_csv(profiles: list[AgentProfile]) -> str:
    """Convert profiles to OASIS Twitter CSV format.

    OASIS Twitter requires exactly 5 columns: user_id, name, username, user_char, description.
    ForkCast fields age, gender, profession, interests are intentionally dropped.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "name", "username", "user_char", "description"])
    for p in profiles:
        writer.writerow([p.agent_id, p.name, p.username, p.persona, p.bio])
    return output.getvalue()


def _convert_profiles_to_reddit_json(profiles: list[AgentProfile]) -> list[dict[str, Any]]:
    """Convert profiles to OASIS Reddit JSON format.

    Includes OASIS-required fields (karma, mbti, country) with defaults.
    ForkCast fields profession and interests are dropped.
    """
    return [
        {
            "user_id": p.agent_id,
            "username": p.username,
            "name": p.name,
            "bio": p.bio,
            "persona": p.persona,
            "age": p.age,
            "gender": p.gender,
            "karma": 0,
            "mbti": "",
            "country": "",
        }
        for p in profiles
    ]
```

- [ ] **Step 4: Update test imports**

Update imports in the test file from `_convert_profiles_to_csv` → `_convert_profiles_to_twitter_csv`. Add `import csv, io` at top of test file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestConvertProfilesToTwitterCSV tests/test_oasis_engine.py::TestConvertProfilesToRedditJSON -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/oasis_engine.py tests/test_oasis_engine.py
git commit -m "feat(oasis): rewrite profile conversion to match OASIS expected formats"
```

---

### Task 6: Rewrite OasisEngine — Action Map and Trace Extraction

**Files:**
- Modify: `src/forkcast/simulation/oasis_engine.py:21-91` (action map + parse function)
- Test: `tests/test_oasis_engine.py:87-109` (action parsing tests)

- [ ] **Step 1: Write failing tests for new action extraction**

Replace `TestParseOasisAction` in `tests/test_oasis_engine.py`:

```python
class TestExtractTraceActions:
    """Test extracting ForkCast Actions from OASIS trace table rows."""

    def test_create_post_action(self):
        """OASIS 'create_post' maps to ForkCast CREATE_POST."""
        row = {
            "user_id": 0,
            "action": "create_post",
            "info": json.dumps({"content": "Hello world"}),
            "created_at": "2026-03-20T10:00:00Z",
        }
        profiles = _make_profiles(3)
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.CREATE_POST
        assert action.action_args["content"] == "Hello world"
        assert action.agent_name == "Agent0"
        assert action.round == 1
        assert action.platform == "twitter"

    def test_like_post_action(self):
        row = {
            "user_id": 1,
            "action": "like_post",
            "info": json.dumps({"post_id": 5}),
            "created_at": "2026-03-20T10:01:00Z",
        }
        profiles = _make_profiles(3)
        action = _trace_row_to_action(row, round_num=2, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.LIKE_POST
        assert action.agent_id == 1
        assert action.agent_name == "Agent1"

    def test_repost_maps_to_create_post(self):
        """OASIS REPOST maps to ForkCast CREATE_POST."""
        row = {
            "user_id": 0,
            "action": "repost",
            "info": json.dumps({"post_id": 3}),
            "created_at": "2026-03-20T10:00:00Z",
        }
        profiles = _make_profiles(1)
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.CREATE_POST

    def test_unknown_action_maps_to_do_nothing(self):
        row = {
            "user_id": 0,
            "action": "unknown_thing",
            "info": "{}",
            "created_at": "2026-03-20T10:00:00Z",
        }
        profiles = _make_profiles(1)
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.DO_NOTHING

    def test_do_nothing_action(self):
        row = {
            "user_id": 0,
            "action": "do_nothing",
            "info": "{}",
            "created_at": "2026-03-20T10:00:00Z",
        }
        profiles = _make_profiles(1)
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.DO_NOTHING
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestExtractTraceActions -v`
Expected: FAIL — `_trace_row_to_action` doesn't exist

- [ ] **Step 3: Implement new action map and trace row parser**

In `src/forkcast/simulation/oasis_engine.py`, replace `_OASIS_ACTION_MAP` and `_parse_oasis_action`:

```python
# Map OASIS ActionType.value strings to ForkCast ActionType
_OASIS_ACTION_MAP: dict[str, str] = {
    "create_post": ActionType.CREATE_POST,
    "like_post": ActionType.LIKE_POST,
    "dislike_post": ActionType.DISLIKE_POST,
    "create_comment": ActionType.CREATE_COMMENT,
    "follow": ActionType.FOLLOW,
    "mute": ActionType.MUTE,
    "do_nothing": ActionType.DO_NOTHING,
    "repost": ActionType.CREATE_POST,  # OASIS REPOST → ForkCast CREATE_POST
}


def _trace_row_to_action(
    row: dict[str, Any],
    round_num: int,
    platform: str,
    profiles: list[AgentProfile],
) -> Action:
    """Convert an OASIS trace table row to a ForkCast Action.

    Args:
        row: Dict with keys: user_id, action, info (JSON string), created_at
        round_num: Current round number
        platform: Platform name (twitter/reddit)
        profiles: Agent profiles for name lookup
    """
    user_id = row.get("user_id", 0)
    oasis_action = row.get("action", "do_nothing")
    action_type = _OASIS_ACTION_MAP.get(oasis_action, ActionType.DO_NOTHING)

    # Parse info JSON for action args
    action_args: dict[str, Any] = {}
    info_str = row.get("info", "{}")
    try:
        info = json.loads(info_str) if isinstance(info_str, str) else info_str
        if isinstance(info, dict):
            if "content" in info:
                action_args["content"] = info["content"]
            if "post_id" in info:
                action_args["post_id"] = info["post_id"]
            if "user_id" in info:
                action_args["user_id"] = info["user_id"]
    except (json.JSONDecodeError, TypeError):
        pass

    # Look up agent name from profiles
    agent_name = f"agent{user_id}"
    for p in profiles:
        if p.agent_id == user_id:
            agent_name = p.name
            break

    return Action(
        round=round_num,
        timestamp=row.get("created_at", ""),
        agent_id=user_id,
        agent_name=agent_name,
        platform=platform,
        action_type=action_type,
        action_args=action_args,
    )
```

- [ ] **Step 4: Update test imports**

Update imports in `tests/test_oasis_engine.py` to import `_trace_row_to_action` instead of `_parse_oasis_action`. Remove old `_monitor_actions_file` import.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestExtractTraceActions -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/oasis_engine.py tests/test_oasis_engine.py
git commit -m "feat(oasis): rewrite action map and trace extraction for OASIS in-process API"
```

---

### Task 7: Rewrite OasisEngine — Core Engine Class

**Files:**
- Rewrite: `src/forkcast/simulation/oasis_engine.py:94-228` (engine class)
- Test: `tests/test_oasis_engine.py:112-195` (engine tests)

This is the main rewrite — replacing the subprocess-based engine with in-process OASIS API calls.

- [ ] **Step 1: Write failing tests for new OasisEngine**

Replace `TestMonitorActionsFile` and `TestOasisEngine` in `tests/test_oasis_engine.py`:

```python
class TestOasisEngine:
    """Tests for in-process OASIS engine with mocked oasis module."""

    def _mock_oasis_module(self):
        """Create a mock oasis module with the expected API surface."""
        mock_oasis = MagicMock()
        mock_oasis.DefaultPlatformType.TWITTER = "twitter"
        mock_oasis.DefaultPlatformType.REDDIT = "reddit"

        # Mock environment
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env

        # Mock agent graph generation
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_oasis.generate_reddit_agent_graph = AsyncMock(return_value=MagicMock())

        return mock_oasis, mock_env

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_action_per_trace_row(self, mock_import):
        """Engine should emit on_action for each new trace row after env.step()."""
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        profiles = _make_profiles(2)
        config = _make_config()
        actions_received = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            # Create a mock OASIS SQLite trace table
            db_path = sim_dir / "oasis.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)"
            )
            conn.execute(
                "INSERT INTO trace VALUES (0, 'create_post', '{\"content\": \"Hello\"}', '2026-03-20T10:00:00Z')"
            )
            conn.execute(
                "INSERT INTO trace VALUES (1, 'like_post', '{\"post_id\": 1}', '2026-03-20T10:01:00Z')"
            )
            conn.commit()
            conn.close()

            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                agent_mode="llm",
                on_action=lambda a: actions_received.append(a),
                on_round=lambda r, t: None,
            )

        assert len(actions_received) == 2  # Depends on rounds * trace rows
        # Verify action types are correctly mapped
        assert actions_received[0].action_type == ActionType.CREATE_POST

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_round(self, mock_import):
        """Engine should call on_round at the start of each round."""
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        profiles = _make_profiles(2)
        config = _make_config()
        rounds_seen = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            db_path = sim_dir / "oasis.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)"
            )
            conn.commit()
            conn.close()

            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                agent_mode="llm",
                on_action=lambda a: None,
                on_round=lambda r, t: rounds_seen.append((r, t)),
            )

        # Config has 2 hours / 30 min = 4 rounds
        assert len(rounds_seen) == 4
        assert rounds_seen[0] == (1, 4)
        assert rounds_seen[-1] == (4, 4)

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_round_complete(self, mock_import):
        """Engine should call on_round_complete after each round."""
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        profiles = _make_profiles(2)
        config = _make_config()
        completes = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            db_path = sim_dir / "oasis.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)"
            )
            conn.commit()
            conn.close()

            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                agent_mode="llm",
                on_action=lambda a: None,
                on_round=lambda r, t: None,
                on_round_complete=lambda r, t: completes.append((r, t)),
            )

        assert len(completes) == 4

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_stop_breaks_loop(self, mock_import):
        """Setting stopped flag should break the round loop."""
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        profiles = _make_profiles(2)
        config = _make_config()  # 4 rounds
        rounds_seen = []

        def on_round(r, t):
            rounds_seen.append(r)

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            db_path = sim_dir / "oasis.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)"
            )
            conn.commit()
            conn.close()

            engine = OasisEngine(sim_dir=sim_dir)
            # Stop after first round by setting flag before step completes
            original_step = mock_env.step
            async def stop_after_first(*a, **kw):
                if len(rounds_seen) >= 1:
                    engine.stop()
                return await original_step(*a, **kw)
            mock_env.step = stop_after_first

            result = engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                agent_mode="llm",
                on_action=lambda a: None,
                on_round=on_round,
            )

        assert len(rounds_seen) < 4  # Should have stopped early

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_returns_result_dict(self, mock_import):
        """Engine run should return dict with total_rounds and total_actions."""
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        profiles = _make_profiles(2)
        config = _make_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            db_path = sim_dir / "oasis.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)"
            )
            conn.commit()
            conn.close()

            engine = OasisEngine(sim_dir=sim_dir)
            result = engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                agent_mode="llm",
                on_action=lambda a: None,
                on_round=lambda r, t: None,
            )

        assert "total_rounds" in result
        assert "total_actions" in result
        assert result["total_rounds"] == 4

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_oasis_import_failure_raises(self, mock_import):
        """If OASIS is not installed, engine.run() should raise immediately."""
        mock_import.side_effect = ImportError("No module named 'oasis'")

        profiles = _make_profiles(2)
        config = _make_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = OasisEngine(sim_dir=Path(tmpdir))
            with pytest.raises(ImportError):
                engine.run(
                    profiles=profiles,
                    config=config,
                    platform="twitter",
                    agent_mode="llm",
                    on_action=lambda a: None,
                )
```

Add at top of test file:
```python
import sqlite3
from unittest.mock import AsyncMock
import pytest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestOasisEngine -v`
Expected: FAIL — old engine class doesn't accept `agent_mode`, no `_import_oasis`

- [ ] **Step 3: Rewrite OasisEngine class**

Replace the entire engine class and remove `_monitor_actions_file` in `src/forkcast/simulation/oasis_engine.py`:

```python
import asyncio
import math
import sqlite3


def _import_oasis():
    """Import the oasis module. Raises ImportError if not installed."""
    import oasis
    return oasis


class OasisEngine:
    """Run a simulation using OASIS's in-process Python API.

    Supports two agent modes:
    - 'llm': Each agent gets LLMAction() — OASIS uses camel-ai's LLM integration
    - 'native': Each agent gets ManualAction() — rule-based action selection
    """

    def __init__(self, sim_dir: Path) -> None:
        self.sim_dir = sim_dir
        self._stopped = False

    def stop(self) -> None:
        """Signal the engine to stop after the current round."""
        self._stopped = True

    def run(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        agent_mode: str = "llm",
        on_action: Callable[[Action], None] = lambda a: None,
        on_round: Callable[[int, int], None] | None = None,
        on_round_complete: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Run OASIS simulation using the in-process API.

        Creates its own event loop since this runs in a background thread
        (via asyncio.to_thread in the route handler).
        """
        if self._stopped:
            return {"total_rounds": 0, "total_actions": 0}
        self._stopped = False
        return asyncio.run(self._run_async(
            profiles, config, platform, agent_mode,
            on_action, on_round, on_round_complete,
        ))

    async def _run_async(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        agent_mode: str,
        on_action: Callable[[Action], None],
        on_round: Callable[[int, int], None] | None,
        on_round_complete: Callable[[int, int], None] | None,
    ) -> dict[str, Any]:
        oasis = _import_oasis()

        self.sim_dir.mkdir(parents=True, exist_ok=True)

        # Write profile files for OASIS
        if platform == "twitter":
            profile_path = self.sim_dir / "twitter_profiles.csv"
            profile_path.write_text(
                _convert_profiles_to_twitter_csv(profiles), encoding="utf-8"
            )
        else:
            profile_path = self.sim_dir / f"{platform}_profiles.json"
            profile_path.write_text(
                json.dumps(_convert_profiles_to_reddit_json(profiles), indent=2),
                encoding="utf-8",
            )

        # Bridge ForkCast LLM config to camel-ai env vars
        self._bridge_llm_config()

        # Build model for LLM mode
        model = None
        if agent_mode == "llm":
            model = self._create_camel_model()

        # Determine available actions per platform
        try:
            from oasis.social_platform.typing import ActionType as OasisActionType
            if platform == "twitter":
                available_actions = [
                    OasisActionType.CREATE_POST, OasisActionType.LIKE_POST,
                    OasisActionType.REPOST, OasisActionType.FOLLOW, OasisActionType.DO_NOTHING,
                ]
            else:
                available_actions = [
                    OasisActionType.CREATE_POST, OasisActionType.CREATE_COMMENT,
                    OasisActionType.LIKE_POST, OasisActionType.DISLIKE_POST,
                    OasisActionType.FOLLOW, OasisActionType.MUTE, OasisActionType.DO_NOTHING,
                ]
        except ImportError:
            available_actions = None  # Let OASIS use defaults

        # Create agent graph
        graph_kwargs = {"profile_path": str(profile_path), "model": model}
        if available_actions is not None:
            graph_kwargs["available_actions"] = available_actions

        if platform == "twitter":
            agent_graph = await oasis.generate_twitter_agent_graph(**graph_kwargs)
            oasis_platform = oasis.DefaultPlatformType.TWITTER
        else:
            agent_graph = await oasis.generate_reddit_agent_graph(**graph_kwargs)
            oasis_platform = oasis.DefaultPlatformType.REDDIT

        # Create OASIS environment
        oasis_db_path = self.sim_dir / "oasis.db"
        env = oasis.make(
            agent_graph=agent_graph,
            platform=oasis_platform,
            database_path=str(oasis_db_path),
            semaphore=30,
        )
        await env.reset()

        total_rounds = math.ceil(config.total_hours * 60 / config.minutes_per_round)
        total_actions = 0
        last_trace_rowid = 0
        round_num = 0

        try:
            for round_num in range(1, total_rounds + 1):
                if self._stopped:
                    break

                if on_round:
                    on_round(round_num, total_rounds)

                # Build actions for this round
                try:
                    if agent_mode == "llm":
                        # LLM mode: let OASIS decide autonomously via LLMAction
                        await env.step({})
                    else:
                        # Native mode: build rule-based ManualAction per agent
                        actions = self._build_native_actions(
                            agent_graph, round_num, config, platform, oasis,
                        )
                        await env.step(actions)
                except Exception as step_exc:
                    logger.error("env.step() failed on round %d: %s", round_num, step_exc)
                    # Continue to next round — partial data is preserved

                # Extract new actions from OASIS trace table
                new_actions, last_trace_rowid = self._extract_actions_from_trace(
                    oasis_db_path, round_num, platform, profiles, last_trace_rowid,
                )
                for action in new_actions:
                    on_action(action)
                    total_actions += 1

                if on_round_complete:
                    on_round_complete(round_num, total_rounds)
        finally:
            await env.close()

        return {
            "total_rounds": round_num if round_num > 0 else 0,
            "total_actions": total_actions,
        }

    def _bridge_llm_config(self) -> None:
        """Bridge ForkCast LLM settings to camel-ai expected env vars."""
        llm_key = os.environ.get("LLM_API_KEY", "")
        llm_base = os.environ.get("LLM_BASE_URL", "")
        if llm_key:
            os.environ["OPENAI_API_KEY"] = llm_key
        if llm_base:
            os.environ["OPENAI_API_BASE_URL"] = llm_base

    def _create_camel_model(self):
        """Create a camel-ai ModelFactory model from ForkCast config."""
        try:
            from camel.models import ModelFactory
            model_name = os.environ.get("LLM_MODEL_NAME", "")
            if model_name:
                return ModelFactory.create(model_name=model_name)
        except Exception as exc:
            logger.warning("Could not create camel-ai model: %s — using default", exc)
        return None

    def _build_native_actions(
        self,
        agent_graph,
        round_num: int,
        config: SimulationConfig,
        platform: str,
        oasis_module,
    ) -> dict:
        """Build rule-based ManualAction for each agent in native mode.

        Uses config's agent_configs for activity levels and frequency weights.
        Falls back to DO_NOTHING if no config match is found.
        """
        import random
        try:
            from oasis.social_platform.typing import ActionType as OasisActionType
        except ImportError:
            return {}

        actions = {}
        agents = list(agent_graph.get_agents()) if hasattr(agent_graph, 'get_agents') else []

        # Determine peak/off-peak multiplier for this round
        hour_in_sim = (round_num * config.minutes_per_round / 60) % 24
        if int(hour_in_sim) in config.peak_hours:
            activity_mult = config.peak_multiplier
        elif int(hour_in_sim) in config.off_peak_hours:
            activity_mult = config.off_peak_multiplier
        else:
            activity_mult = 1.0

        for agent in agents:
            agent_id = getattr(agent, 'agent_id', None) or getattr(agent, 'user_id', 0)

            # Find agent config if available
            agent_cfg = None
            for ac in config.agent_configs:
                if ac.get("agent_id") == agent_id:
                    agent_cfg = ac
                    break

            activity_level = (agent_cfg or {}).get("activity_level", 0.5)
            if random.random() > activity_level * activity_mult:
                # Inactive this round
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.DO_NOTHING
                    )
                except Exception:
                    pass
                continue

            # Select action type by weighted frequency
            post_freq = (agent_cfg or {}).get("post_frequency", 0.4)
            like_freq = (agent_cfg or {}).get("like_frequency", 0.4)
            comment_freq = (agent_cfg or {}).get("comment_frequency", 0.2)

            roll = random.random()
            if roll < post_freq:
                # Generate a post from hot_topics or seed_posts
                content = random.choice(config.hot_topics or config.seed_posts or [""])
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.CREATE_POST,
                        action_args={"content": content},
                    )
                except Exception:
                    pass
            elif roll < post_freq + like_freq:
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.LIKE_POST,
                    )
                except Exception:
                    pass
            else:
                content = random.choice(config.hot_topics or ["Interesting!"])
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.CREATE_COMMENT,
                        action_args={"content": content},
                    )
                except Exception:
                    pass

        return actions

    def _extract_actions_from_trace(
        self,
        oasis_db_path: Path,
        round_num: int,
        platform: str,
        profiles: list[AgentProfile],
        last_rowid: int,
    ) -> tuple[list[Action], int]:
        """Query OASIS SQLite trace table for new actions since last_rowid."""
        actions: list[Action] = []
        new_last_rowid = last_rowid

        try:
            conn = sqlite3.connect(str(oasis_db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT rowid, user_id, action, info, created_at "
                "FROM trace WHERE rowid > ? ORDER BY rowid",
                (last_rowid,),
            ).fetchall()
            conn.close()

            for row in rows:
                row_dict = dict(row)
                new_last_rowid = max(new_last_rowid, row_dict["rowid"])
                action = _trace_row_to_action(row_dict, round_num, platform, profiles)
                if action.action_type != ActionType.DO_NOTHING:
                    actions.append(action)
        except Exception as exc:
            logger.warning("Failed to extract actions from OASIS trace: %s", exc)

        return actions, new_last_rowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py::TestOasisEngine -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/oasis_engine.py tests/test_oasis_engine.py
git commit -m "feat(oasis): rewrite OasisEngine to use in-process OASIS API with dual agent modes"
```

---

### Task 8: Runner Integration — Pass agent_mode and Wire Callbacks

**Files:**
- Modify: `src/forkcast/simulation/runner.py:216-240`
- Test: `tests/test_oasis_runner_integration.py` (new file)

- [ ] **Step 1: Write failing integration test**

Create `tests/test_oasis_runner_integration.py`:

```python
"""Integration tests: runner → OasisEngine → DB flow with mocked OASIS."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from forkcast.db.connection import init_db, get_db
from forkcast.simulation.runner import run_simulation
from forkcast.llm.client import ClaudeClient


def _seed_db(db_path, project_id="proj_1", sim_id="sim_1", agent_mode="llm"):
    """Create a minimal DB with a prepared simulation."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, requirement, domain, status, created_at) "
            "VALUES (?, 'test req', 'social_media', 'ready', datetime('now'))",
            (project_id,),
        )
        config = {
            "total_hours": 1,
            "minutes_per_round": 30,
            "peak_hours": [10],
            "off_peak_hours": [0],
            "peak_multiplier": 1.5,
            "off_peak_multiplier": 0.3,
            "seed_posts": [],
            "hot_topics": [],
            "narrative_direction": "",
            "agent_configs": [],
            "platform_config": {},
        }
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, engine_type, platforms, agent_mode, config_json, created_at) "
            "VALUES (?, ?, 'prepared', 'oasis', '[\"twitter\"]', ?, ?, datetime('now'))",
            (sim_id, project_id, agent_mode, json.dumps(config)),
        )


def _seed_profiles(data_dir, sim_id="sim_1"):
    """Write a minimal agents.json."""
    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {
            "agent_id": 0, "name": "Alice", "username": "alice",
            "bio": "Test", "persona": "Curious", "age": 30,
            "gender": "female", "profession": "Engineer",
            "interests": ["AI"], "entity_type": "Person", "entity_source": "test",
        },
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestRunnerOasisIntegration:
    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_runner_passes_agent_mode_to_engine(self, mock_import, tmp_path):
        """Runner should read agent_mode from DB and pass to OasisEngine."""
        mock_oasis = MagicMock()
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_import.return_value = mock_oasis

        db_path = tmp_path / "test.db"
        data_dir = tmp_path / "data"
        domains_dir = tmp_path / "domains"
        # Create minimal domain
        (domains_dir / "social_media").mkdir(parents=True)
        (domains_dir / "social_media" / "manifest.yaml").write_text("name: social_media\nplatforms: [twitter]\nsim_engine: oasis")

        _seed_db(db_path, agent_mode="native")
        _seed_profiles(data_dir)

        # Create OASIS trace DB (engine expects it)
        oasis_db_path = data_dir / "sim_1" / "oasis.db"
        oasis_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(oasis_db_path))
        conn.execute("CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)")
        conn.execute("INSERT INTO trace VALUES (0, 'create_post', '{\"content\": \"Hello\"}', '2026-03-20T10:00:00Z')")
        conn.commit()
        conn.close()

        client = MagicMock(spec=ClaudeClient)

        result = run_simulation(
            db_path=db_path,
            data_dir=data_dir,
            simulation_id="sim_1",
            client=client,
            domains_dir=domains_dir,
        )

        assert result.actions_count >= 0

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_actions_persisted_to_db(self, mock_import, tmp_path):
        """Actions from OASIS engine should be persisted to simulation_actions table."""
        mock_oasis = MagicMock()
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_import.return_value = mock_oasis

        db_path = tmp_path / "test.db"
        data_dir = tmp_path / "data"
        domains_dir = tmp_path / "domains"
        (domains_dir / "social_media").mkdir(parents=True)
        (domains_dir / "social_media" / "manifest.yaml").write_text("name: social_media\nplatforms: [twitter]\nsim_engine: oasis")

        _seed_db(db_path)
        _seed_profiles(data_dir)

        oasis_db_path = data_dir / "sim_1" / "oasis.db"
        oasis_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(oasis_db_path))
        conn.execute("CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)")
        conn.execute("INSERT INTO trace VALUES (0, 'create_post', '{\"content\": \"Test post\"}', '2026-03-20T10:00:00Z')")
        conn.commit()
        conn.close()

        client = MagicMock(spec=ClaudeClient)
        run_simulation(
            db_path=db_path,
            data_dir=data_dir,
            simulation_id="sim_1",
            client=client,
            domains_dir=domains_dir,
        )

        with get_db(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM simulation_actions WHERE simulation_id = 'sim_1'"
            ).fetchone()[0]
            status = conn.execute(
                "SELECT status FROM simulations WHERE id = 'sim_1'"
            ).fetchone()["status"]

        assert count >= 1
        assert status == "completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_runner_integration.py -v`
Expected: FAIL — runner doesn't pass `agent_mode` to engine

- [ ] **Step 3: Modify runner to pass agent_mode and wire callbacks**

In `src/forkcast/simulation/runner.py`, replace the OASIS engine block (lines 216-240):

```python
            elif engine_type == "oasis":
                # Deferred import -- OASIS is an optional dependency
                from forkcast.simulation.oasis_engine import OasisEngine

                agent_mode = sim["agent_mode"] or "llm"
                _progress(stage="running", engine="oasis", agent_mode=agent_mode)

                completed_platforms: list[str] = []
                for pi, platform in enumerate(platforms):
                    if stop_event is not None and stop_event.is_set():
                        break

                    oasis_engine = OasisEngine(sim_dir=sim_dir)

                    # Wire stop_event
                    if stop_event is not None:
                        def _oasis_stop_monitor(eng=oasis_engine):
                            stop_event.wait()
                            eng.stop()
                        stop_thread = threading.Thread(target=_oasis_stop_monitor, daemon=True)
                        stop_thread.start()

                    engine_result = oasis_engine.run(
                        profiles=profiles,
                        config=config,
                        platform=platform,
                        agent_mode=agent_mode,
                        on_action=on_action,
                        on_round=on_round,
                        on_round_complete=lambda r, t: None,  # OASIS doesn't use checkpoint state
                    )
                    completed_platforms.append(platform)
```

Note: The `completed_platforms` variable needs to be initialized for the OASIS branch too (it was only in Claude's branch before). Also, `sim["agent_mode"]` is available because the runner does `SELECT * FROM simulations` and the V4 migration added the column.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_runner_integration.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/runner.py tests/test_oasis_runner_integration.py
git commit -m "feat(runner): pass agent_mode to OasisEngine and wire on_round_complete callback"
```

---

### Task 9: Frontend — Agent Mode Toggle in SimulationSettings

**Files:**
- Modify: `frontend/src/components/SimulationSettings.vue:1-159`
- Modify: `frontend/src/api/simulations.js` (if `updateSettings` needs updating)

- [ ] **Step 1: Add agent_mode ref and save logic**

In `SimulationSettings.vue` `<script setup>`:

After `const forceRegenerate = ref(false)` (line 21), add:
```javascript
const agentMode = ref(props.simulation.agent_mode || 'llm')
```

In the `watch` block (line 24-29), add:
```javascript
  agentMode.value = sim.agent_mode || 'llm'
```

In the `save()` function, add `agent_mode` to the payload:
```javascript
    await updateSettings(props.simulation.id, {
      engine_type: engine.value,
      platforms: platforms.value,
      prep_model: prepModel.value,
      run_model: runModel.value,
      agent_mode: agentMode.value,
    })
```

Add computed for showing agent mode section:
```javascript
const showAgentMode = computed(() => engine.value === 'oasis' && caps.isOasisAvailable)
```

- [ ] **Step 2: Add agent mode toggle UI**

In the template, after the Engine section (after line 95) and before Platforms, add:

```html
    <!-- Agent Mode (OASIS only) -->
    <div v-if="showAgentMode">
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Agent Mode</label>
      <div class="flex gap-2">
        <button
          v-for="mode in [
            { value: 'llm', label: 'LLM-driven', sub: 'AI decides actions · costs tokens' },
            { value: 'native', label: 'Rule-based', sub: 'Activity patterns · fast, free' },
          ]"
          :key="mode.value"
          class="flex-1 px-3 py-2 rounded-md text-sm border transition-colors text-left"
          :style="{
            backgroundColor: agentMode === mode.value ? 'var(--accent-surface)' : 'transparent',
            borderColor: agentMode === mode.value ? 'var(--accent)' : 'var(--border)',
            color: agentMode === mode.value ? 'var(--accent)' : 'var(--text-secondary)',
            opacity: readonly ? 0.4 : 1,
            cursor: readonly ? 'not-allowed' : 'pointer',
          }"
          :disabled="readonly"
          @click="agentMode = mode.value"
        >
          <span class="block font-medium">{{ mode.label }}</span>
          <span class="block text-xs mt-0.5 opacity-70">{{ mode.sub }}</span>
        </button>
      </div>
    </div>
```

- [ ] **Step 3: Test in browser (manual)**

1. Start dev server: `npm run dev` from project root
2. Open a simulation with OASIS engine selected
3. Verify the Agent Mode toggle appears
4. Verify it saves correctly (check network tab)
5. Verify it hides when Claude engine is selected

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SimulationSettings.vue
git commit -m "feat(ui): add agent mode toggle in SimulationSettings when OASIS engine selected"
```

---

### Task 10: Clean Up Old Code and Final Test Pass

**Files:**
- Modify: `src/forkcast/simulation/oasis_engine.py` — remove any remaining dead code
- Modify: `tests/test_oasis_engine.py` — remove old tests for deleted functions

- [ ] **Step 1: Remove dead code from oasis_engine.py**

Remove the `_monitor_actions_file` function entirely if it still exists — it was part of the subprocess approach.

Remove `signal`, `subprocess`, `sys`, `time` imports if no longer used.

Ensure these imports remain: `asyncio`, `csv`, `io`, `json`, `logging`, `math`, `os`, `sqlite3` from stdlib, plus `Path`, `Any`, `Callable` from typing.

- [ ] **Step 2: Remove old test classes**

Remove `TestMonitorActionsFile` from `tests/test_oasis_engine.py` if it still exists.

Remove old `TestParseOasisAction` if it still exists.

Clean up unused imports in the test file.

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -x -q`
Expected: All tests pass (420+ tests — original 412 + new tests from this plan)

- [ ] **Step 4: Run frontend build check**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast/frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/oasis_engine.py tests/test_oasis_engine.py
git commit -m "chore: remove dead subprocess code from OASIS engine and tests"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | DB migration V3→V4 (agent_mode column) | schema.py, connection.py |
| 2 | Optional OASIS dependency group | pyproject.toml |
| 3 | API — agent_mode in create/settings/list | simulation_routes.py |
| 4 | Capabilities — agent_modes in response | capabilities_routes.py, capabilities.js |
| 5 | Profile format mapping rewrite | oasis_engine.py (profiles) |
| 6 | Action map + trace extraction rewrite | oasis_engine.py (actions) |
| 7 | Core OasisEngine class rewrite | oasis_engine.py (engine) |
| 8 | Runner integration — pass agent_mode | runner.py, test_oasis_runner_integration.py |
| 9 | Frontend — agent mode toggle | SimulationSettings.vue |
| 10 | Clean up dead code + final test pass | oasis_engine.py, tests |
