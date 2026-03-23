# ForkCast — Technical Architecture

**Version:** v0.8.0-phase7b | **Last updated:** 2026-03-23

## System Overview

ForkCast is a collective intelligence simulation platform. The pipeline takes seed documents and a prediction question, builds a knowledge graph, generates AI agent personas, runs multi-round social media simulations, and produces analytical reports.

```
Documents + Requirement
        │
        ▼
┌─────────────────┐
│  Graph Building  │  Extract text → Chunk → Ontology → Entities → Graph + Vector Store
└────────┬────────┘
         ▼
┌─────────────────┐
│   Preparation    │  Graph entities → Persona generation → Simulation config
└────────┬────────┘
         ▼
┌─────────────────┐
│   Simulation     │  Multi-round agent loop: post, comment, like, follow, mute, do-nothing
└────────┬────────┘
         ▼
┌─────────────────┐
│     Report       │  Tool-use loop: research simulation data → write analysis
└────────┬────────┘
         ▼
┌─────────────────┐
│   Evaluation     │  16 gates (programmatic) + 7 LLM judgments → scorecard
└─────────────────┘
```


## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| API | FastAPI + uvicorn, SSE streaming via sse-starlette |
| Frontend | Vue 3 + Vite, Pinia, Tailwind CSS, D3.js |
| CLI | Typer |
| Database | SQLite (WAL mode, row_factory) |
| LLM | Anthropic Claude API (claude-sonnet-4-6 default) |
| Graph | NetworkX (DiGraph) |
| Vector store | ChromaDB (sentence-transformers/all-MiniLM-L6-v2) |
| Simulation | Claude engine (native) + OASIS engine (optional, camel-oasis in-process API) |
| Templates | Jinja2 |
| PDF parsing | pypdf |
| Package manager | uv (Python), npm (frontend) |
| Testing | pytest |


## Source Layout

```
src/forkcast/
├── config.py              # Settings singleton (env vars, paths)
├── db/
│   ├── connection.py      # SQLite connection manager + schema migration
│   ├── schema.py          # Table definitions (v1→v4), indexes, foreign keys
│   └── queries.py         # Shared query helpers (get_project_domain, get_domain_for_simulation)
├── llm/
│   ├── client.py          # ClaudeClient: complete, tool_use, think, stream, smart_call + retry
│   └── utils.py           # strip_code_fences helper
├── graph/
│   ├── pipeline.py        # Graph build orchestrator
│   ├── text_extractor.py  # PDF/MD/TXT → plain text
│   ├── chunker.py         # Overlapping text chunks (1000 chars, 200 overlap)
│   ├── ontology.py        # LLM-generated entity/relationship types
│   ├── entity_extractor.py # Tool-use entity extraction from chunks
│   ├── graph_store.py     # NetworkX serialization + DB registration
│   └── vector_store.py    # ChromaDB indexing (chunks + entities)
├── simulation/
│   ├── models.py          # AgentProfile, SimulationConfig, PrepareResult, RunResult
│   ├── prepare.py         # Load graph → generate profiles → generate config + profile reuse
│   ├── profile_generator.py # LLM extended-thinking persona generation
│   ├── config_generator.py  # LLM extended-thinking simulation parameters
│   ├── claude_engine.py   # Agent tool-use loop (7 action tools)
│   ├── oasis_engine.py    # OASIS in-process API engine (camel-oasis, llm + native modes)
│   ├── runner.py          # Engine selection, round loop, action recording, checkpoint/resume
│   ├── action.py          # Action dataclass + ActionType enum
│   └── state.py           # SimulationState: feed, posts, followers, mutes, visibility
├── report/
│   ├── models.py          # ReportResult, StreamEvent, ToolContext
│   ├── pipeline.py        # Tool-use loop orchestrator
│   ├── tools.py           # 5 report tools: graph_search, graph_explore, simulation_data, interview_agent, agent_actions
│   ├── chat.py            # Report Q&A (multi-turn, tool-enabled)
│   └── agent_chat.py      # Direct agent chat (in-character)
├── eval/
│   ├── gates.py           # 16 programmatic gates (Layer 1)
│   ├── judgments.py       # 7 LLM quality judgments (Layer 2)
│   ├── runner.py          # Evaluation orchestrator
│   ├── scorecard.py       # Assembly, persistence, comparison
│   └── rubrics/           # 7 markdown rubric templates
├── domains/
│   ├── loader.py          # Domain manifest + prompt resolution with _default fallback
│   └── scaffold.py        # Generate new domain directory structure
├── api/
│   ├── app.py             # FastAPI factory with DB lifespan + CORS
│   ├── project_routes.py  # /api/projects CRUD + file upload
│   ├── graph_routes.py    # /api/projects/{id}/build-graph + graph data + SSE
│   ├── simulation_routes.py # /api/simulations CRUD + prepare/start/stop/settings + SSE
│   ├── report_routes.py   # /api/reports generate/list/get/export + chat endpoints
│   ├── domain_routes.py   # /api/domains list + scaffold
│   ├── capabilities_routes.py # /api/capabilities (models, engines, agent_modes)
│   └── responses.py       # success/error response helpers
└── cli/
    ├── main.py            # Typer entry point, registers all subcommands
    ├── project_cmd.py     # forkcast project {create,list,get,delete}
    ├── sim_cmd.py         # forkcast sim {create,prepare,run,list,get,actions}
    ├── report_cmd.py      # forkcast report {generate,list,get,export}
    ├── chat_cmd.py        # forkcast chat {report,agent}
    ├── eval_cmd.py        # forkcast eval {run,compare}
    ├── domain_cmd.py      # forkcast domain {list,create,get}
    └── server_cmd.py      # forkcast server run

frontend/
├── index.html
├── vite.config.js         # Dev proxy /api → localhost:5001
├── src/
│   ├── main.js            # Vue + Pinia + Router setup
│   ├── App.vue
│   ├── router/index.js    # Routes: / → projects, /project/:id → tabs
│   ├── stores/
│   │   ├── project.js     # Pinia store: projects, graphs, simulations, SSE progress
│   │   └── capabilities.js # Models, engines, agent_modes from /api/capabilities
│   ├── api/
│   │   ├── client.js      # Base fetch wrapper
│   │   ├── projects.js    # Project CRUD
│   │   ├── graphs.js      # Graph build + data
│   │   ├── simulations.js # Simulation lifecycle
│   │   ├── reports.js     # Report generation + chat
│   │   └── capabilities.js
│   ├── views/
│   │   ├── ProjectListView.vue   # Dashboard: project cards + create
│   │   ├── ProjectWizard.vue     # 3-step creation wizard
│   │   ├── ProjectLayout.vue     # Tab container: Overview, Graph, Simulation, Report
│   │   ├── OverviewTab.vue       # Project details + files
│   │   ├── GraphTab.vue          # D3 force-directed graph + search/filter
│   │   ├── SimulationTab.vue     # 5-state lifecycle: empty/configuring/running/complete/viewing
│   │   └── ReportTab.vue         # Report generation + markdown render + chat
│   └── components/
│       ├── AppShell.vue          # Top-level layout with sidebar rail
│       ├── IconRail.vue          # Navigation sidebar
│       ├── SimulationSettings.vue # Engine, platform, model, agent_mode, profile reuse
│       ├── SimulationConfigView.vue # Read-only config display
│       ├── LiveFeed.vue          # Real-time action stream during simulation
│       ├── ProgressPanel.vue     # SSE progress display (graph/sim/report)
│       ├── AgentAvatar.vue       # Deterministic color avatar from name hash
│       └── ...                   # Toast, EmptyState, StatCard, etc.
```


## Database Schema (v4)

```sql
-- Key-value metadata (schema version tracking)
meta (key TEXT PK, value TEXT)

-- Projects: top-level container for a prediction scenario
projects (
    id TEXT PK,              -- "proj_" + hex
    domain TEXT,             -- domain plugin name (e.g., "social-media", "_default")
    name TEXT,
    status TEXT,             -- created → graph_built → completed
    requirement TEXT,        -- natural language prediction question
    ontology_json TEXT,      -- LLM-generated entity/relationship types (JSON)
    created_at TEXT,
    updated_at TEXT
)

-- Uploaded source documents
project_files (
    id INTEGER PK AUTOINCREMENT,
    project_id TEXT FK → projects,
    filename TEXT,
    path TEXT,               -- relative path in data/{project_id}/uploads/
    text_content TEXT,       -- extracted plain text
    size INTEGER,
    created_at TEXT
)

-- Knowledge graphs built from documents
graphs (
    id TEXT PK,
    project_id TEXT FK → projects,
    status TEXT,
    node_count INTEGER,
    edge_count INTEGER,
    file_path TEXT,          -- path to graph.json
    created_at TEXT,
    updated_at TEXT
)

-- Simulations: one per project+engine+platform combination
simulations (
    id TEXT PK,              -- "sim_" + hex
    project_id TEXT FK → projects,
    graph_id TEXT FK → graphs,
    status TEXT,             -- created → prepared → running → completed
    engine_type TEXT,        -- "claude" or "oasis"
    platforms TEXT,          -- JSON array: ["twitter", "reddit"]
    config_json TEXT,        -- serialized SimulationConfig
    agent_mode TEXT,         -- "llm" (default) or "native" (OASIS rule-based)
    created_at TEXT,
    updated_at TEXT
)

-- Individual agent actions during simulation
simulation_actions (
    id INTEGER PK AUTOINCREMENT,
    simulation_id TEXT FK → simulations,
    round INTEGER,
    agent_id INTEGER,
    agent_name TEXT,
    action_type TEXT,        -- CREATE_POST, LIKE_POST, CREATE_COMMENT, FOLLOW_USER, etc.
    content TEXT,            -- JSON action payload
    platform TEXT,
    timestamp TEXT
)
-- INDEX: (simulation_id, round, agent_id)

-- Generated analysis reports
reports (
    id TEXT PK,              -- "report_" + hex
    simulation_id TEXT FK → simulations,
    status TEXT,             -- generating → completed | failed
    tool_history_json TEXT,  -- JSON array of tool calls made during generation
    content_markdown TEXT,   -- final report content
    created_at TEXT,
    completed_at TEXT
)

-- Multi-turn chat conversations
chat_history (
    id INTEGER PK AUTOINCREMENT,
    conversation_id TEXT,    -- groups messages in a conversation
    role TEXT,               -- "user" | "assistant"
    message TEXT,
    tool_calls_json TEXT,
    timestamp TEXT
)
-- INDEX: (conversation_id)

-- LLM token accounting
token_usage (
    id INTEGER PK AUTOINCREMENT,
    project_id TEXT FK → projects,
    stage TEXT,              -- "graph", "ontology", "profiles", "config", "simulation", "report"
    input_tokens INTEGER,
    output_tokens INTEGER,
    model TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

**Migration path:** v1→v2 (add graphs/token_usage tables), v2→v3 (add model column to simulations), v3→v4 (add agent_mode column to simulations).


## Domain Plugin System

Domains customize pipeline behavior through prompts, hints, and configuration.

```
domains/
├── _default/                  # Fallback domain (always present)
│   ├── manifest.yaml          # name, sim_engine, platforms, prompt paths
│   ├── prompts/
│   │   ├── ontology.md        # Entity type generation guidance
│   │   ├── persona.md         # Agent profile generation (Jinja2: entity_name, entity_type, requirement, ...)
│   │   ├── config_gen.md      # Simulation parameter generation
│   │   ├── report_guidelines.md # Report analyst guidelines
│   │   └── agent_system.md    # Per-agent system prompt (Jinja2: agent_name, username, persona)
│   ├── ontology/
│   │   └── hints.yaml         # Seed entity types for the LLM
│   └── simulation/
│       └── platform_defaults.yaml
└── social-media/              # Domain-specific overrides
    └── (same structure — loader falls back to _default for missing files)
```

**Resolution order:** domain-specific file → `_default` file → error

**Key manifest fields:**
- `sim_engine`: `"claude"` or `"oasis"` — CLI reads this as default when `--engine` not specified
- `platforms`: `["twitter"]` or `["twitter", "reddit"]`
- `prompts`: maps prompt names to file paths within the domain directory


## LLM Integration

`ClaudeClient` wraps the Anthropic SDK with five calling patterns:

| Method | Use case | Example |
|--------|----------|---------|
| `complete()` | Single response | Ontology generation, eval judgments |
| `tool_use()` | Structured output | Entity extraction, report generation, agent actions |
| `think()` | Extended reasoning | Persona generation (budget=8000), config generation (budget=10000) |
| `stream()` | Real-time output | Report generation SSE, chat responses |
| `smart_call()` | Auto-dispatch | Selects complete/tool_use/think based on args |

**Retry logic:** Exponential backoff (1s, 2s, 4s) on rate limits and 500+ errors, max 3 retries.

**Default model:** `claude-sonnet-4-6` (configurable per-call)


## Data Flows

### 1. Graph Building

```
Upload files → text_extractor (PDF/MD/TXT → plain text)
    → chunker (1000 char chunks, 200 overlap, sentence boundaries)
    → ontology.py: Claude complete() with domain hints → entity_types + relationship_types
    → entity_extractor: Claude tool_use() per chunk → entities + relationships
    → deduplicate entities (name + type)
    → graph_store: build NetworkX DiGraph → save graph.json + register in DB
    → vector_store: ChromaDB index chunks + entities
```

### 2. Persona Generation + Simulation

```
Load graph entities
    → Check for reusable profiles (same project + graph + domain):
        If found and force_regenerate=false → copy agents.json from prior simulation
        Else → for each entity:
            profile_generator: Claude think() with domain persona.md template
                → AgentProfile (name, username, bio, persona, age, gender, profession, interests)
                → Incremental save to agents.json (crash recovery)
    → config_generator: Claude think() with domain config_gen.md
        → SimulationConfig (rounds, timing, topics, platform config)
    → runner selects engine by engine_type:
        Claude engine: for each round, for each agent:
            Claude tool_use() with 7 action tools
                → Action recorded to JSONL + simulation_actions table
                → SimulationState updated (feed, posts, followers, mutes)
        OASIS engine: for each platform:
            Convert profiles → OASIS format (CSV for Twitter, JSON for Reddit)
            oasis.make() → env with agent graph
            For each round: env.step(actions)
                → Extract new actions from OASIS SQLite trace table
                → Map OASIS action types to ForkCast ActionType
                → Action recorded to JSONL + simulation_actions table
    → Checkpoint written after each completed round (resume on crash)
```

### 3. Report Generation

```
Load context: profiles, graph, ChromaDB, simulation summary
    → Build system prompt: domain report_guidelines + simulation summary JSON
    → Tool-use loop (max 10 rounds):
        Claude tool_use() with REPORT_TOOLS
        → Execute: graph_search, graph_explore, simulation_data, interview_agent, agent_actions
        → Append tool results to messages
        → Continue until no more tool calls
    → Final text → reports.content_markdown
```

### 4. Evaluation

```
Load pipeline outputs:
    ontology from projects.ontology_json
    personas from data/{sim_id}/profiles/agents.json
    actions from simulation_actions table
    report from reports.content_markdown
    graph entities from data/{project_id}/graph.json

Layer 1 — Gates (16, no LLM calls, ~50ms):
    Ontology:    min_entity_types(3), valid_json
    Persona:     count_matches_entities, required_fields, unique_names
    Simulation:  min_actions, no_empty_rounds, action_diversity(3), all_agents_active,
                 has_interactions, do_nothing_ratio(<0.7)
    Report:      min_length(500), has_sections(3), references_agents(2),
                 no_template_artifacts, valid_markdown

Layer 2 — Judgments (7, LLM calls, ~45s):
    Only run if ALL gates pass.
    Each: load rubric.md → Jinja2 render with content → Claude complete() → parse {score, justification}

Scorecard: {eval_id, gates, quality, summary: {gates_passed, quality_avg, weakest}}
    → Persist to data/{project_id}/evals/{eval_id}.json
```


## Data Directory Layout

```
data/
├── forkcast.db                          # SQLite database
├── {project_id}/
│   ├── uploads/                         # Source documents
│   │   ├── report.pdf
│   │   └── article.md
│   ├── graph.json                       # NetworkX DiGraph serialization
│   ├── chroma/                          # ChromaDB persistent store
│   └── evals/
│       └── eval_{id}.json               # Evaluation scorecards
└── {simulation_id}/
    ├── profiles/
    │   └── agents.json                  # Generated agent profiles
    ├── config.json                      # Simulation configuration
    └── actions.jsonl                    # Action log (one JSON object per line)
```


## API Endpoints

### Projects
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects` | Create project (multipart: domain, requirement, files) |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project details + files |

### Graph Building
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/build-graph` | Trigger graph building |
| GET | `/api/projects/{id}/build-graph/stream` | SSE progress stream |
| GET | `/api/projects/{id}/graph` | Get graph metadata |
| GET | `/api/projects/{id}/graph/data` | Get full graph nodes + edges (for D3) |

### Simulations
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/simulations` | Create simulation (engine_type, platforms, agent_mode) |
| GET | `/api/simulations` | List simulations |
| GET | `/api/simulations/{id}` | Get simulation details |
| PATCH | `/api/simulations/{id}/settings` | Update engine, platforms, model, agent_mode |
| POST | `/api/simulations/{id}/prepare` | Generate profiles + config (force_regenerate opt) |
| GET | `/api/simulations/{id}/prepare/stream` | SSE prepare progress |
| POST | `/api/simulations/{id}/start` | Start simulation |
| GET | `/api/simulations/{id}/run/stream` | SSE run progress + actions |
| POST | `/api/simulations/{id}/stop` | Stop simulation |
| GET | `/api/simulations/{id}/actions` | Get all actions |

### Reports
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/reports/generate` | Generate report |
| GET | `/api/reports/{id}/generate/stream` | SSE generation progress |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/{id}` | Get report with content + tool history |
| GET | `/api/reports/{id}/export` | Download as markdown |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat/report` | Chat with report agent (SSE) |
| POST | `/api/chat/agent` | Chat with simulation agent (SSE) |

### Domains
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/domains` | List domain plugins |
| POST | `/api/domains` | Scaffold new domain |

### Capabilities
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capabilities` | Available models, engines, agent_modes |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |


## CLI Commands

```
forkcast project create FILES --domain DOMAIN --prompt REQUIREMENT [--name NAME]
forkcast project list
forkcast project get PROJECT_ID
forkcast project delete PROJECT_ID

forkcast sim create PROJECT_ID [--engine ENGINE] [--platforms PLATFORMS]
forkcast sim prepare SIMULATION_ID
forkcast sim run SIMULATION_ID [--max-rounds N]
forkcast sim list | get | actions

forkcast report generate SIMULATION_ID [--max-tool-rounds N]
forkcast report list | get | export

forkcast chat report REPORT_ID
forkcast chat agent SIMULATION_ID AGENT_ID

forkcast eval run PROJECT_ID [--simulation-id SIM_ID] [--gates-only]
forkcast eval compare EVAL_FILE_1 EVAL_FILE_2

forkcast domain list | create | get
forkcast server run [--host HOST] [--port PORT]
```


## Simulation Engines

### Claude Engine (default)

Each agent is an LLM tool-use call per round. The agent receives the current feed state, its persona, and 7 action tools (create_post, like_post, dislike_post, create_comment, follow_user, mute_user, do_nothing). SimulationState tracks the social graph in-memory. Actions are recorded to JSONL + SQLite.

### OASIS Engine (optional)

Uses camel-oasis's in-process Python API. Supports two agent modes:

- **`llm`**: Each agent gets `LLMAction()` — OASIS delegates to camel-ai's LLM integration
- **`native`**: Each agent gets `ManualAction()` — rule-based action selection using activity levels, post/like frequencies, and peak hours from SimulationConfig

**Key implementation details:**
- Profiles converted to OASIS format (CSV for Twitter, JSON for Reddit)
- `oasis.make()` creates the environment with an agent graph
- After each `env.step()`, new actions extracted from OASIS's internal SQLite trace table
- OASIS action types mapped to ForkCast ActionType via `_OASIS_ACTION_MAP`
- `OPENAI_API_KEY` must be set (even in native mode) — bridged from `LLM_API_KEY` / `ANTHROPIC_API_KEY` or a placeholder
- Install via `scripts/install-oasis.sh` (handles camel-oasis pytest conflict via `--no-deps`)

### Profile Reuse

When preparing a new simulation, `find_reusable_profiles()` searches for the most recent simulation in the same project with matching `graph_id` and `domain` that has an `agents.json` file. If found and `force_regenerate=false` (the default), profiles are copied instead of regenerated via LLM. The UI exposes this as a "Regenerate profiles" checkbox in SimulationSettings.


## Configuration

All settings via environment variables (loaded from `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `FORKCAST_DATA_DIR` | `{project_root}/data` | Runtime data directory |
| `FORKCAST_DOMAINS_DIR` | `{project_root}/domains` | Domain plugins directory |
| `FORKCAST_DB_NAME` | `forkcast.db` | SQLite database filename |
| `FORKCAST_HOST` | `127.0.0.1` | API server host |
| `FORKCAST_PORT` | `5001` | API server port |
| `FORKCAST_LOG_LEVEL` | `info` | Logging level |


## Dependencies

**Core:** fastapi, uvicorn, typer, anthropic, networkx, chromadb, sentence-transformers, jinja2, pyyaml, python-dotenv, httpx, pypdf, python-multipart, sse-starlette

**Optional (OASIS):** camel-oasis, camel-ai, igraph, pandas, neo4j, cairocffi, prance, openapi-spec-validator, requests-oauthlib, slack-sdk, unstructured

**Frontend:** vue 3, vite, pinia, tailwindcss, d3, vue-router, marked (markdown rendering)

**Dev:** pytest, pytest-asyncio
