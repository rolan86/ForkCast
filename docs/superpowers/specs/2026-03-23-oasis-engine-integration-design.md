# OASIS Engine Integration Design

## Problem

ForkCast's OASIS engine currently launches `python -m oasis.run` as a subprocess — a CLI that doesn't exist in the `camel-oasis` package. OASIS simulations "complete" with 0 actions every time. Reports generated from these simulations have no data to analyze.

The real OASIS API (`camel-oasis` v0.2.5 + `camel-ai` v0.2.78) is an in-process Python library: you create an environment with `oasis.make()`, step through rounds with `env.step(actions)`, and read results from OASIS's internal SQLite database.

## Goal

Rewrite `OasisEngine` to use OASIS's actual Python API so that OASIS simulations produce real action data that flows through to the report pipeline, LiveFeed, and all existing UI components.

## Architecture

### Engine Selection

The user selects `claude` or `oasis` engine in the SimulationSettings panel (existing UI). When `oasis` is selected, a new **Agent Mode** toggle appears:

- **LLM-driven** (`llm`): Each active agent is given `LLMAction()` per round. OASIS uses camel-ai's LLM integration to decide what each agent does autonomously. Richer, more emergent behavior. Costs tokens.
- **Rule-based** (`native`): Each active agent is given `ManualAction()` with action type and content determined by rule-based logic (config activity patterns, post frequencies, sentiment biases). Fast, no token cost, less emergent.

Both modes share the same OASIS social platform simulation (feeds, viral mechanics, follower graphs). The difference is only in how agent decisions are made.

### Data Flow

Identical to the Claude engine — no changes downstream:

```
OasisEngine.run()
  → on_action(Action) callback per action
    → runner appends to all_actions list
    → runner writes to actions.jsonl
    → runner emits SSE progress event
  → on_round() callback per round
    → runner emits SSE round event
  → runner persists all_actions to simulation_actions table
  → LiveFeed, Report tools, View Actions all work unchanged
```

## OasisEngine Implementation

### Lifecycle

1. **Setup**: Write profiles in OASIS-expected format, create agent graph, create environment
2. **Round loop**: For each round, determine active agents, build actions dict, call `env.step()`, extract new actions from OASIS's trace table, emit callbacks
3. **Cleanup**: `env.close()` on completion or stop

### Profile Format Mapping

ForkCast's `AgentProfile` fields must be mapped to OASIS's expected format:

**Twitter (CSV)** — OASIS Twitter requires exactly 5 columns. ForkCast fields `age`, `gender`, `profession`, `interests` are intentionally dropped because OASIS's Twitter CSV schema does not support them. The persona field (`user_char`) carries enough context for agent behavior.

| ForkCast field | OASIS field |
|---|---|
| `agent_id` | `user_id` |
| `name` | `name` |
| `username` | `username` |
| `persona` | `user_char` |
| `bio` | `description` |

**Reddit (JSON)**:
| ForkCast field | OASIS field |
|---|---|
| `agent_id` | `user_id` |
| `username` | `username` |
| `name` | `name` |
| `bio` | `bio` |
| `persona` | `persona` |
| `age` | `age` |
| `gender` | `gender` |
| `profession` | (dropped — not in OASIS Reddit schema) |
| `interests` | (dropped) |
| (default 0) | `karma` |
| (default "") | `mbti` |
| (default "") | `country` |

### Agent Graph Creation

```python
# Twitter
agent_graph = await generate_twitter_agent_graph(
    profile_path=twitter_csv_path,
    model=model,  # camel-ai ModelFactory model (LLM mode only)
    available_actions=TWITTER_ACTIONS,
)

# Reddit
agent_graph = await generate_reddit_agent_graph(
    profile_path=reddit_json_path,
    model=model,
    available_actions=REDDIT_ACTIONS,
)
```

Available actions per platform (using OASIS `ActionType` enum):
- **Twitter**: `CREATE_POST`, `LIKE_POST`, `REPOST`, `FOLLOW`, `DO_NOTHING`
- **Reddit**: `CREATE_POST`, `CREATE_COMMENT`, `LIKE_POST`, `DISLIKE_POST`, `FOLLOW`, `MUTE`, `DO_NOTHING`

**Action type mapping**: OASIS's `ActionType.REPOST` does not exist in ForkCast's `ActionType`. It maps to `CREATE_POST` in ForkCast (same as current `_OASIS_ACTION_MAP` which maps `"retweet"` → `CREATE_POST`). No new `ActionType` values are added — the existing map is updated to use OASIS's actual `ActionType` enum values instead of string guesses.

### Environment Creation

```python
env = oasis.make(
    agent_graph=agent_graph,
    platform=oasis.DefaultPlatformType.TWITTER,  # or REDDIT
    database_path=str(oasis_db_path),
    semaphore=30,  # Limit concurrent LLM requests
)
await env.reset()
```

### Round Loop

```python
for round_num in range(1, total_rounds + 1):
    if self._stopped:
        break

    active_agents = self._determine_active_agents(round_num, config)

    if agent_mode == "llm":
        actions = {agent: LLMAction() for agent in active_agents}
    else:  # native
        actions = self._build_native_actions(active_agents, round_num, config, state)

    await env.step(actions)

    new_actions = self._extract_actions_from_trace(round_num, platform, last_trace_id)
    for action in new_actions:
        on_action(action)

    on_round(round_num, total_rounds)
```

### Action Extraction

After each `env.step()`, query OASIS's SQLite trace table:

```sql
SELECT user_id, info, created_at, action
FROM trace
WHERE rowid > ?
ORDER BY rowid
```

Map each row to a ForkCast `Action`:
- `action` column → `action_type` via `_OASIS_ACTION_MAP`. The map must be updated to use OASIS's actual `ActionType.value` strings (e.g., `"create_post"`, `"like_post"`, etc.) since the current map guesses string names. The exact strings will be confirmed during implementation by inspecting `ActionType` enum values from the installed `camel-oasis` package.
- `info` column → parse for `content`, `post_id`, `user_id` → `action_args`
- `user_id` → `agent_id` + look up `agent_name` from profiles
- `round_num` from loop counter
- `created_at` → `timestamp`

### Native Mode Action Logic

Rule-based action selection using config's `agent_configs`:

1. Roll probability based on agent's `activity_level` and current peak/off-peak multiplier
2. If active this round, select action type weighted by agent's configured frequencies (post vs comment vs like)
3. Generate simple content: for posts, pick from `hot_topics` or `seed_posts` with agent's `sentiment_bias` applied; for comments/likes, target existing posts
4. Wrap as `ManualAction(action_type=..., action_args=...)`
5. If no activity this round → `ManualAction(action_type=ActionType.DO_NOTHING)`

### Engine Interface

The new `OasisEngine.run()` signature:

```python
def run(
    self,
    profiles: list[AgentProfile],
    config: SimulationConfig,
    platform: str,
    agent_mode: str,  # "llm" or "native"
    on_action: Callable[[Action], None],
    on_round: Callable[[int, int], None] | None = None,
    on_round_complete: Callable[[int], None] | None = None,
) -> dict[str, Any]:
```

The runner reads `agent_mode` from the simulation DB record (`sim["agent_mode"]`) and passes it to the engine. The runner already does `SELECT *` on the simulations table, so `agent_mode` is available once the column exists.

`on_round_complete` is called after each round, just like in the Claude engine. The runner uses it for checkpoint writing. This means OASIS engine runs support crash recovery/resume via the existing checkpoint system.

### Async Considerations

OASIS's API is async (`await env.step()`). The simulation runner calls engines from a background thread (via `asyncio.to_thread()` in the route handler). Since this thread has no running event loop, `asyncio.run()` is safe to use internally. The engine creates its own event loop for OASIS calls:

```python
def run(self, ...):
    return asyncio.run(self._run_async(...))

async def _run_async(self, ...):
    # All OASIS async calls happen here
    env = oasis.make(...)
    await env.reset()
    for round_num in range(1, total_rounds + 1):
        await env.step(actions)
        ...
    await env.close()
```

**Constraint**: `OasisEngine.run()` must NOT be called from an async context (where an event loop is already running). This is already the case — the runner is always invoked via `asyncio.to_thread()` from the FastAPI route handler.

## Dependencies

Added as optional install group in `pyproject.toml`:

```toml
[project.optional-dependencies]
oasis = [
    "camel-oasis>=0.2.5",
    "camel-ai>=0.2.78",
]
```

ForkCast works without these installed. The capabilities endpoint returns `oasis.available: false` when the import fails (existing behavior).

### LLM Configuration Bridge

OASIS (via camel-ai) uses `ModelFactory` which reads standard OpenAI env vars. ForkCast has its own `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME`. Before creating the OASIS environment, bridge these:

```python
os.environ["OPENAI_API_KEY"] = settings.llm_api_key
os.environ["OPENAI_API_BASE_URL"] = settings.llm_base_url
```

**Model name**: The `generate_*_agent_graph()` functions take a `model` parameter (camel-ai `ModelFactory` model). ForkCast's `LLM_MODEL_NAME` is an OpenAI-compatible model name (e.g., `gpt-4o`, `claude-sonnet-4-6` via proxy). The engine will construct the camel-ai model using `ModelFactory.create()` with the configured model name. If the model name is not recognized by camel-ai, the engine falls back to camel-ai's default model. In **native mode**, no model is needed — `model=None` is passed to `generate_*_agent_graph()` since agents don't use LLM.

This bridges ForkCast's config to camel-ai's expectations without requiring duplicate env vars.

## Database Migration

**V4 migration**: Add `agent_mode` column to `simulations` table.

Changes in `schema.py`:
- `SCHEMA_VERSION` updated from `3` to `4`
- `TABLES_V4` constant added (fresh-install schema including `agent_mode` column)
- `MIGRATION_V3_TO_V4` constant:
  ```sql
  ALTER TABLE simulations ADD COLUMN agent_mode TEXT DEFAULT 'llm';
  UPDATE meta SET value = '4' WHERE key = 'schema_version';
  ```
- `ensure_schema()` in `connection.py` chains the new migration: if current version is 3, apply V3→V4

Existing rows default to `'llm'`. The column stores `'llm'` or `'native'`.

## API Changes

### POST /api/simulations

Add `agent_mode` to `CreateSimulationRequest`:

```python
class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str | None = None
    platforms: list[str] | None = None
    agent_mode: str | None = None  # NEW: "llm" or "native"
```

When `agent_mode` is not provided, default to `"llm"`. Validate that `agent_mode` is one of `["llm", "native"]` — return 400 for invalid values.

### PATCH /api/simulations/{id}/settings

Add `agent_mode` to `UpdateSettingsRequest`:

```python
class UpdateSettingsRequest(BaseModel):
    engine_type: str | None = None
    platforms: list[str] | None = None
    prep_model: str | None = None
    run_model: str | None = None
    agent_mode: str | None = None  # NEW: "llm" or "native"
```

Same validation: `agent_mode` must be `"llm"` or `"native"` if provided.

### GET /api/capabilities

Extend OASIS section:

```json
{
  "engines": {
    "claude": {"available": true},
    "oasis": {
      "available": true,
      "agent_modes": ["llm", "native"]
    }
  }
}
```

## Frontend Changes

### SimulationSettings Panel

When engine is `oasis` and OASIS is available:

- Show **Agent Mode** toggle (radio buttons or segmented control)
- **LLM-driven**: label + subtitle "Agents use AI to decide actions. Richer interactions, costs tokens."
- **Rule-based**: label + subtitle "Agents follow activity patterns. Fast, no token cost."
- Default: `llm`

No changes to LiveFeed, simulation table, viewing state, report tab, or any other component.

## Error Handling

- **OASIS not installed**: Capabilities returns `available: false`, UI greys out OASIS. If triggered via API directly, fail fast with clear error before starting — never silently "complete" with 0 actions.
- **env.step() failure**: Catch per-round, log error, persist partial actions collected so far, mark simulation as `failed` with descriptive message.
- **LLM failures in LLM mode**: OASIS handles retries internally via camel-ai. If an agent's call fails, that agent gets skipped for the round.
- **Native mode failures**: Fallback to `DO_NOTHING` for the agent.
- **0 actions at completion**: If engine ran successfully but produced 0 actions (all DO_NOTHING), that's legitimate — status is `completed`. If engine failed to initialize or run, status is `failed`.

## Testing

### Unit Tests (mock OASIS)

- `test_oasis_engine.py` — rewrite existing tests with mocked `oasis` module:
  - Profile format mapping (ForkCast → OASIS fields)
  - Action extraction from trace table → ForkCast `Action` objects
  - `on_action` callback invoked per action
  - LLM mode uses `LLMAction()`, native mode uses `ManualAction()`
  - Stop signal respected between rounds
  - Error handling: env creation failure, step failure
  - Active agent selection (peak/off-peak)

- `test_oasis_runner_integration.py` — runner → engine → DB flow with mocked OASIS:
  - Actions persist to `simulation_actions` table
  - Actions written to `actions.jsonl`
  - Status set to `completed` (success) or `failed` (error)
  - `agent_mode` read from simulation record and passed to engine

### Manual Verification

After implementation, with `camel-oasis` installed:
1. Create simulation with OASIS engine + LLM mode
2. Prepare and run — verify actions appear in LiveFeed
3. View Actions on completed sim — verify content visible
4. Generate report — verify report tools can query action data
5. Repeat with native mode — verify faster execution, simpler content

## Files Changed

- **Rewrite**: `src/forkcast/simulation/oasis_engine.py` — in-process OASIS API
- **Modify**: `src/forkcast/simulation/runner.py` — pass `agent_mode` to engine
- **Modify**: `src/forkcast/api/simulation_routes.py` — `agent_mode` in create/settings/list
- **Modify**: `src/forkcast/api/capabilities_routes.py` — `agent_modes` in response
- **Modify**: `src/forkcast/db/schema.py` — V4 migration adding `agent_mode`
- **Modify**: `src/forkcast/db/connection.py` — chain V3→V4 migration in `ensure_schema()`
- **Modify**: `frontend/src/components/SimulationSettings.vue` — agent mode toggle
- **Modify**: `frontend/src/stores/capabilities.js` — expose `agent_modes` from capabilities response
- **Modify**: `pyproject.toml` — optional `[oasis]` dependency group
- **Rewrite**: `tests/test_oasis_engine.py` — new tests for in-process API
- **New**: `tests/test_oasis_runner_integration.py` — runner integration tests
