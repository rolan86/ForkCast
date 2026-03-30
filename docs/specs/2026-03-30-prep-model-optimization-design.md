# Preparation Model Optimization

## Problem

Simulation preparation (persona generation) uses claude-sonnet-4-6 by default with extended thinking enabled, generating one persona per LLM call. For a typical simulation with 22 entities, this means:

- 22 separate Sonnet API calls, each with 8K thinking budget
- ~61K input + ~104K output tokens per preparation
- ~45 minutes wall time
- Estimated ~$1.50 per concept in API costs

The persona generation task is creative/generative (produce character profiles), not reasoning-heavy. It doesn't benefit from extended thinking or Sonnet-level reasoning.

## Goals

1. **Default to Haiku** for persona generation — ~15x cheaper, faster
2. **User-selectable model** — exposed in CLI, API, and frontend
3. **Batch persona generation** — reduce API calls from N to ~N/6
4. **Remove extended thinking** from persona generation (keep it for config gen)
5. **Token usage observability** — log, display, and surface token consumption at every layer

## Non-Goals

- Changing the model for config generation (keeps Sonnet + thinking)
- Changing the model for graph building, simulation runs, or report generation
- Restructuring the domain prompt template system
- Changing the persona quality criteria or prompt content

## Design

### 1. Model Selection

#### Default Prep Model

Add `DEFAULT_PREP_MODEL = "claude-haiku-4-5"` to `config.py`.

The `prep_model` only controls persona generation. Config generation continues to use `client.default_model` (Sonnet) with thinking enabled — see Section 1.1 for the split.

The `factory.py` default model stays as Sonnet — it's correct for graph building, simulation runs, report generation, and config generation. The prep model override is isolated to persona generation only.

#### 1.1. Model Split: Personas vs Config

Currently, `prepare.py` passes `prep_model` to both `generate_profiles()` and `generate_config()`. This must change:

- `generate_profiles_batched()` receives `prep_model` (defaults to `DEFAULT_PREP_MODEL` / Haiku)
- `generate_config()` receives `None` — so it falls through to `client.default_model` (Sonnet) and keeps `smart_call(thinking_budget=10000)`

In `prepare.py`, the config generation call changes from:
```python
# Before:
config, config_tokens = generate_config(client=client, ..., model=prep_model)

# After:
config, config_tokens = generate_config(client=client, ..., model=None)
```

This ensures config gen always uses Sonnet with thinking regardless of the user's prep model choice.

#### API

`POST /api/simulations` (`CreateSimulationRequest`): Add optional `prep_model: str | None = None` field to the Pydantic model:

```python
class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str | None = None
    platforms: list[str] | None = None
    agent_mode: str | None = None
    prep_model: str | None = None  # NEW
```

When provided, stored in the `simulations.prep_model` column via the INSERT query. When NULL, defaults to `DEFAULT_PREP_MODEL` at preparation time.

The INSERT in `create_simulation()` (simulation_routes.py ~line 93-97) must be updated:
```python
# Add prep_model to INSERT columns and values
conn.execute(
    "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, "
    "prep_model, agent_mode, created_at) VALUES (?, ?, ?, 'created', ?, ?, ?, ?, datetime('now'))",
    (sim_id, project_id, graph_id, engine_type, json.dumps(platforms), prep_model, agent_mode),
)
```

`PATCH /api/simulations/{id}/settings`: Already supports `prep_model`. No change needed.

#### Frontend

In the simulation settings panel (shown before clicking "Prepare"), add a model dropdown:
- Label: "Preparation Model"
- Options: populated from `AVAILABLE_MODELS` in config
- Default selection: `claude-haiku-4-5`
- Hint text: "Haiku is faster and cheaper. Sonnet produces richer personas."

#### CLI (SeedCast)

`forge push` gains `--prep-model` flag:
```
forge push <run-id> --all --auto-simulate --prep-model claude-sonnet-4-6
```

Default (no flag): no `prep_model` sent to ForkCast, which then defaults to Haiku.

`ForkCastClient.create_simulation()` gains `prep_model: str | None` parameter, passed in the JSON body.

### 2. Batched Persona Generation

#### Batch Size

6 personas per LLM call. For 22 entities: 4 batches (6 + 6 + 6 + 4).

#### Prompt Structure

New template `domains/_default/prompts/persona_batch.md` wraps multiple entities:

```markdown
Generate detailed simulation personas for the following {{ count }} entities.
Return a JSON array of {{ count }} objects, one per entity, in the same order.

Each object must have keys: name, username, bio, persona, age, gender, profession, interests.

{% for entity in entities %}
## Entity {{ loop.index }}: {{ entity.name }}
Type: {{ entity.type }}
Description: {{ entity.description }}
Related entities: {{ entity.related }}

{% endfor %}

## Scenario Context
The simulation is exploring: {{ requirement }}

Shape each persona's perspectives and priorities around this scenario.
```

**Domain loader update:** Add `"persona_batch": "prompts/persona_batch.md"` to `DEFAULT_PROMPT_FILES` in `domains/loader.py` and to `PROMPT_KEYS`. This ensures `read_prompt(domain, "persona_batch")` resolves correctly with the standard domain fallback chain.

The existing single-entity `persona.md` template is kept for domain-specific customization reference but is no longer called directly by the preparation code.

#### Wiring in prepare.py

`prepare.py` must be updated to load the batch template and call the new function:

```python
# Load batch persona template (replaces single persona template)
persona_batch_template = read_prompt(domain, "persona_batch")

# Call batched generation instead of generate_profiles()
profiles, token_records = generate_profiles_batched(
    client=client,
    entities=entities,
    graph_data=graph_data,
    requirement=project["requirement"],
    persona_batch_template=persona_batch_template,
    profiles_dir=profiles_dir,
    on_progress=on_progress_adapter,
    model=prep_model,
)
```

The `on_progress` adapter lambda must be updated to match the new callback signature:

```python
# Before: lambda current, total: _progress("generating_profile", current=current, total=total)
# After:
def on_progress_adapter(stage: str, **kwargs):
    _progress(stage, **kwargs)
```

#### Generation Flow

Import `DEFAULT_PREP_MODEL` from `forkcast.config` in `profile_generator.py`.

```python
from forkcast.config import DEFAULT_PREP_MODEL

def generate_profiles_batched(
    client, entities, graph_data, requirement,
    persona_batch_template, profiles_dir,
    on_progress=None, model=None, batch_size=6,
) -> tuple[list[AgentProfile], list[dict]]:
    """Generate profiles in batches. Returns (profiles, per_batch_token_records)."""
    existing = load_existing_profiles(profiles_dir)
    remaining = [e for e in entities if e["name"] not in existing]
    batches = [remaining[i:i+batch_size] for i in range(0, len(remaining), batch_size)]

    profiles = _reload_existing(profiles_dir)
    token_records = []

    for batch_idx, batch in enumerate(batches):
        # Enrich each entity with related entities from the graph
        enriched = []
        for entity in batch:
            related = _get_related_entities(entity["name"], graph_data)
            enriched.append({**entity, "related": ", ".join(related) if related else "None"})

        batch_profiles, tokens = _generate_batch(
            client, enriched, requirement,
            persona_batch_template, model, start_agent_id=len(profiles),
        )
        profiles.extend(batch_profiles)
        token_records.append(tokens)
        save_profiles(profiles, profiles_dir)
        if on_progress:
            on_progress("profile_batch", batch=batch_idx+1,
                       total_batches=len(batches),
                       input_tokens=tokens["input"],
                       output_tokens=tokens["output"])

    return profiles, token_records
```

The existing `_get_related_entities()` helper is reused to look up edges per entity before rendering the batch prompt. Each entity dict is enriched with a `related` string field that the template references as `{{ entity.related }}`.

#### LLM Call and max_tokens

Uses `client.complete()` directly — no `smart_call`, no thinking budget. Must set `max_tokens=16000` since 6 persona JSON objects can easily exceed the default 4096:

```python
response = client.complete(
    model=model or DEFAULT_PREP_MODEL,
    messages=[{"role": "user", "content": prompt}],
    system=system,
    max_tokens=16000,
)
```

#### Post-Processing: agent_id, entity_type, entity_source

The LLM returns a JSON array of persona objects (name, username, bio, persona, age, gender, profession, interests). The following fields are NOT generated by the LLM — they are assigned by the caller after parsing:

```python
def _generate_batch(client, entities, requirement,
                    template, model, start_agent_id):
    # ... build prompt, call LLM, parse JSON array ...
    profiles = []
    for i, (data, entity) in enumerate(zip(parsed_array, entities)):
        profile = AgentProfile(
            agent_id=start_agent_id + i,          # Sequential from caller
            entity_type=entity["type"],             # From input entity
            entity_source=entity["name"],           # From input entity
            name=data.get("name", entity["name"]),
            username=data.get("username", ...),
            bio=data.get("bio", ""),
            persona=data.get("persona", ""),
            age=data.get("age", 30),
            gender=data.get("gender", "unspecified"),
            profession=data.get("profession", ""),
            interests=data.get("interests", []),
        )
        profiles.append(profile)
    return profiles, {"input": response.input_tokens, "output": response.output_tokens}
```

The `start_agent_id` parameter ensures IDs are sequential across batches.

Matching is by array index order (prompt says "in the same order"). The entities list and parsed array are zipped together — entity[0] maps to result[0], etc.

#### Fallback

If the JSON array length doesn't match the batch size (LLM skipped or merged entities), retry the missing entities one-at-a-time using a new `_generate_single_fallback()` function that also uses `client.complete(max_tokens=4096)` — NOT the existing `generate_profile()` which uses `smart_call` with thinking. Identify missing entities by checking which `entity_source` names are absent from the parsed results. This is defensive — don't fail the whole batch.

The existing `generate_profile()` function is left unchanged (it's still used by other code paths) but is NOT called from the batched fallback.

#### Crash Recovery

`load_existing_profiles()` returns entity names already generated. On resume, remaining entities are re-batched. Worst case: lose one batch (6 personas) on crash, not all.

### 3. Remove Extended Thinking from Persona Generation

**Changed:**
- `profile_generator.py`: All persona generation calls (batched and fallback single) use `client.complete()` instead of `client.smart_call(thinking_budget=8000)`

**Unchanged:**
- `config_generator.py`: Keeps `smart_call(thinking_budget=10000)` — config gen benefits from reasoning about timing, weights, platform dynamics. Receives `model=None` from `prepare.py` so it always uses Sonnet.
- `graph/pipeline.py`: Keeps thinking for entity extraction and ontology generation
- `report/`: Keeps thinking for research and analysis
- `simulation/`: Keeps thinking for agent action generation

### 4. Token Usage Observability

#### Layer 1: Console/Log Output

During preparation, after each batch completes, emit a progress event via the existing `on_progress` callback:

```json
{"stage": "profile_batch", "batch": 2, "total_batches": 4, "input_tokens": 3200, "output_tokens": 5100, "model": "claude-haiku-4-5"}
```

These events flow through the existing SSE stream (`/api/simulations/{id}/prepare/stream`). Also logged at `INFO` level on the server.

#### Layer 2: Granular DB Records

**Schema change:** Add `simulation_id` column to `token_usage` table. This is required because multiple simulations can exist for the same project, and per-batch stage names would collide without a simulation-level discriminator.

Bump `SCHEMA_VERSION` from 5 to 6 in `db/schema.py`. Add `MIGRATION_V5_TO_V6`:

```sql
ALTER TABLE token_usage ADD COLUMN simulation_id TEXT;
CREATE INDEX IF NOT EXISTS idx_token_usage_simulation_id ON token_usage(simulation_id);
UPDATE meta SET value = '6' WHERE key = 'schema_version';
```

Add the full `TABLES_V6` definition (copy of `TABLES_V5` with `simulation_id TEXT` added to `token_usage` and the index). Update `init_db()` in `db/connection.py` to:
- Use `TABLES_V6` (not `TABLES_V5`) for fresh database creation
- Apply `MIGRATION_V5_TO_V6` when upgrading from V5, following the existing pattern (e.g., V4→V5 migration chain)

Existing rows keep `simulation_id = NULL` (backwards compatible).

Change `prepare.py` from inserting one aggregate `token_usage` row to inserting per-phase rows. The new INSERT for each batch:

```python
conn.execute(
    "INSERT INTO token_usage (project_id, simulation_id, stage, model, input_tokens, output_tokens, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
    (project_id, simulation_id, f"simulation_prep:profile_batch_{batch_idx+1}", prep_model, tokens["input"], tokens["output"]),
)
```

And for config gen:
```python
conn.execute(
    "INSERT INTO token_usage (project_id, simulation_id, stage, model, input_tokens, output_tokens, created_at) "
    "VALUES (?, ?, 'simulation_prep:config', ?, ?, ?, datetime('now'))",
    (project_id, simulation_id, str(client.default_model), config_tokens["input"], config_tokens["output"]),
)
```

`project_id` is kept alongside `simulation_id` for backwards compatibility and for queries that aggregate across all simulations in a project.

Each batch row is inserted immediately after the batch completes (inside the batch loop in `prepare.py`), not all at once at the end. This matches the existing pattern and provides better observability during long-running preparations.

| simulation_id | stage | model | input_tokens | output_tokens |
|--------------|-------|-------|-------------|--------------|
| sim_279e... | `simulation_prep:profile_batch_1` | claude-haiku-4-5 | 2800 | 4200 |
| sim_279e... | `simulation_prep:profile_batch_2` | claude-haiku-4-5 | 3100 | 4800 |
| sim_279e... | `simulation_prep:profile_batch_3` | claude-haiku-4-5 | 2900 | 4500 |
| sim_279e... | `simulation_prep:profile_batch_4` | claude-haiku-4-5 | 2200 | 3100 |
| sim_279e... | `simulation_prep:config` | claude-sonnet-4-6 | 1800 | 2400 |

Note: config row shows `claude-sonnet-4-6` — config gen always uses Sonnet regardless of prep_model.

Aggregate query: `WHERE simulation_id = ? AND stage LIKE 'simulation_prep%'`

Fix: Log actual model used per phase, not `client.default_model`.

#### Layer 3: API Response

Add `token_usage` to `GET /api/simulations/{id}` response:

```json
{
  "data": {
    "id": "sim_...",
    "status": "prepared",
    "token_usage": {
      "preparation": {"input_tokens": 11000, "output_tokens": 16500, "model": "claude-haiku-4-5"},
      "config": {"input_tokens": 1800, "output_tokens": 2400, "model": "claude-sonnet-4-6"}
    }
  }
}
```

Implementation in `get_simulation()`:

```python
# Query token_usage for this simulation
rows = conn.execute(
    "SELECT stage, model, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens "
    "FROM token_usage WHERE simulation_id = ? GROUP BY CASE "
    "WHEN stage LIKE 'simulation_prep:profile%' THEN 'preparation' "
    "WHEN stage LIKE 'simulation_prep:config' THEN 'config' "
    "ELSE stage END, model",
    (simulation_id,),
).fetchall()
```

#### Layer 4: CLI Summary (SeedCast)

After auto-simulate completes each concept, `forge push` prints:

```
  └─ Tokens: 12,400 in / 18,200 out (claude-haiku-4-5)
```

Read from `GET /api/simulations/{id}` response `token_usage` field after pipeline completes.

#### Layer 5: Frontend Display

In the simulation detail/overview, show token usage breakdown by stage. Data comes from the enriched `GET /api/simulations/{id}` response.

## File Changes

### ForkCast

| File | Change |
|------|--------|
| `config.py` | Add `DEFAULT_PREP_MODEL = "claude-haiku-4-5"` |
| `simulation/profile_generator.py` | Import `DEFAULT_PREP_MODEL` from config. Add `generate_profiles_batched()`, `_generate_batch()`, and `_generate_single_fallback()`. Use `client.complete(max_tokens=16000)` for batches, `client.complete(max_tokens=4096)` for fallback. Enrich entities with related data via `_get_related_entities()`. Assign agent_id/entity_type/entity_source post-parse. Return per-batch tokens. |
| `simulation/prepare.py` | Default prep_model to `DEFAULT_PREP_MODEL`, pass `model=None` to `generate_config()`, load `persona_batch` template via `read_prompt()`, update on_progress adapter to new signature, insert per-batch token_usage rows with `simulation_id` and correct model per phase |
| `api/simulation_routes.py` | Add `prep_model: str | None = None` to `CreateSimulationRequest` Pydantic model and persist in INSERT, include token_usage in GET response via simulation_id query |
| `domains/loader.py` | Add `"persona_batch"` to `PROMPT_KEYS` and `DEFAULT_PROMPT_FILES` |
| `domains/_default/prompts/persona_batch.md` | New batch persona template |
| `db/schema.py` | Bump `SCHEMA_VERSION` to 6, add `TABLES_V6` with `simulation_id` in token_usage, add `MIGRATION_V5_TO_V6` (ALTER TABLE + index) |
| `db/connection.py` | Use `TABLES_V6` for fresh DB creation, apply V5→V6 migration in `init_db()` chain |

### SeedCast

| File | Change |
|------|--------|
| `bridges/forkcast_client.py` | Add `prep_model` param to `create_simulation()` |
| `cli/push_cmd.py` | Add `--prep-model` flag, print token summary line from simulation response |

## Testing Strategy

- Unit test: `generate_profiles_batched()` with mocked LLM returning JSON arrays of correct length
- Unit test: Fallback when batch returns wrong count (fewer items than expected)
- Unit test: `agent_id` assignment is sequential across batches
- Unit test: `entity_type` and `entity_source` mapped correctly from input entities
- Unit test: Token usage DB records are per-batch with correct model and simulation_id
- Unit test: Config gen still receives `model=None` and uses Sonnet with thinking
- Unit test: `GET /api/simulations/{id}` includes token_usage aggregated by stage
- Unit test: `POST /api/simulations` persists prep_model in DB
- Unit test: `forge push --prep-model` passes through to API
- Unit test: `max_tokens=16000` is set on batch complete() calls
- Integration test: End-to-end prep with Haiku produces valid profiles
- Verify: Config gen still uses thinking, persona gen does not

## Expected Impact

| Metric | Before | After (Haiku, batched) |
|--------|--------|----------------------|
| Model (personas) | Sonnet 4.6 | Haiku 4.5 |
| Model (config) | Sonnet 4.6 (via prep_model) | Sonnet 4.6 (always, explicit) |
| API calls (22 entities) | 23 (22 + 1 config) | ~5 (4 batches + 1 config) |
| Thinking tokens | ~176K (22 x 8K) | 0 for personas, 10K for config |
| Estimated cost per concept | ~$1.50 | ~$0.05-0.10 |
| Wall time | ~45 min | ~5-10 min |
