# ForkCast — Design Specification

**Date:** 2026-03-20
**Status:** Approved
**Type:** Ground-up build (clean-room implementation)

---

## 1. Vision

ForkCast is a collective intelligence simulation platform. It models how groups of stakeholders think, interact, and influence each other — to surface predictions, test concepts, and reveal narratives that no single analysis could produce.

Unlike traditional prediction tools that ask one AI for an answer, ForkCast creates a digital society of AI agents grounded in real-world entities, gives them distinct perspectives and behavioral patterns, and lets emergent group dynamics reveal insights.

The platform is domain-agnostic. Social media prediction is one use case, but the same engine can model market sentiment, policy impact, organizational dynamics, or narrative evolution. Domains are pluggable. Simulation environments are swappable. Real-world data can blend with simulated data in future versions.

### Target Use Cases

| Use Case | Description |
|----------|-------------|
| Narrative evolution | How does a story, rumor, or news event spread and mutate across communities? |
| Ad copy testing | Which messaging resonates with which audience segments? How do they react and share? |
| Script A/B testing | Test dialogue, storylines, or content variations against simulated audience reactions |
| Tweet/social content A/B testing | Predict engagement, virality, and sentiment before posting |
| Business concept evolution | How do stakeholders (customers, competitors, regulators) respond to a new product or strategy? |
| Business concept testing | Stress-test a business idea against simulated market dynamics |
| Policy impact prediction | How do affected communities react to proposed policies or regulations? |
| Crisis simulation | How does public sentiment evolve during a PR crisis? What interventions work? |

Each use case is served by a domain plugin — a directory of configuration, prompts, and ontology hints that configures ForkCast for that scenario.

---

## 2. Core Workflow

```
User provides seed material + question
         │
         ▼
┌─────────────────────────────┐
│ 1. Knowledge Extraction     │
│    Upload documents →       │
│    LLM ontology generation →│
│    LLM entity extraction →  │
│    Build knowledge graph    │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│ 2. Agent Creation           │
│    Entities → AI personas   │
│    with personality, stance,│
│    behavior patterns        │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│ 3. Simulation               │
│    Agents interact on       │
│    simulated platforms      │
│    (post, comment, react)   │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│ 4. Analysis & Reporting     │
│    LLM analyzes emergent    │
│    behavior, generates      │
│    prediction report        │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│ 5. Deep Interaction         │
│    Chat with analyst or     │
│    individual agents        │
└─────────────────────────────┘
```

---

## 3. Architecture

### Approach: Layered Monolith

Single FastAPI application with clean internal layers. Domain plugins are file-based directories. All components run in one process (except OASIS simulation which runs as a subprocess).

```
┌──────────────────────────────────────────────────────────┐
│                     CLI (forkcast)                        │
│              ┌──────────────────────┐                    │
│              │   FastAPI Server     │◀── Future UI       │
│              └──────────┬───────────┘                    │
│                         │                                │
│  ┌──────────────────────┴─────────────────────────┐     │
│  │            Domain Plugin Loader                  │     │
│  │  domains/{name}/manifest.yaml + prompts/         │     │
│  └──────────────────────┬─────────────────────────┘     │
│                         │                                │
│  ┌──────────┐  ┌───────┴───────┐  ┌───────────────┐    │
│  │  Graph   │  │  Simulation   │  │    Report      │    │
│  │ Pipeline │  │   Engines     │  │   Pipeline     │    │
│  │          │  │               │  │                │    │
│  │ Extract  │  │ ┌───────────┐│  │ Claude LLM-    │    │
│  │ (Claude) │  │ │   OASIS   ││  │ driven with    │    │
│  │ Store    │  │ │(subprocess)││  │ tool access    │    │
│  │(NetworkX)│  │ ├───────────┤│  │ to graph +     │    │
│  │ Search   │  │ │  Claude   ││  │ agents         │    │
│  │(ChromaDB)│  │ │(in-process)││  │                │    │
│  └──────────┘  │ └───────────┘│  └───────────────┘    │
│                └──────────────┘                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Claude API (Anthropic SDK)           │   │
│  │  tool_use │ extended_thinking │ completions       │   │
│  │  Retry, token tracking, cost logging              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────┐  ┌──────────────────────────────────┐   │
│  │  SQLite    │  │  File Storage                     │   │
│  │ forkcast.db│  │  data/{project_id}/               │   │
│  └────────────┘  └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘

External dependency: Claude API only (single API key)
Everything else: local, in-process or subprocess
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Runtime | Python 3.12 | Latest stable |
| Web Framework | FastAPI | Native async, auto OpenAPI docs |
| Database | SQLite | Zero setup, queryable, single file |
| Graph Storage | NetworkX | In-memory graph, JSON serializable |
| Vector Search | ChromaDB (local) | Local embeddings, SQLite-backed |
| Embeddings | sentence-transformers | Local model (all-MiniLM-L6-v2), runs on CPU |
| LLM | Claude API (Anthropic SDK) | Native tool use, extended thinking |
| Simulation | OASIS (subprocess) + Claude (in-process) | Selectable per domain/simulation |
| Real-time | Server-Sent Events | Single persistent connection per operation |
| CLI | Click or Typer | Full workflow from terminal |
| Package Manager | uv | Fast, modern Python package management |

### What's NOT in the Stack

| Excluded | Reason |
|----------|--------|
| Redis / Celery | Overkill for single-server. FastAPI BackgroundTasks sufficient. |
| Kubernetes / Docker | Start simple. Containerize later if needed. |
| TypeScript | Plain JS frontend when UI is built. No compile step needed. |
| LangChain / Pydantic AI | Claude SDK native tool use is simpler and more direct. |
| Neo4j | NetworkX sufficient for expected graph sizes. No server needed. |
| Auth (JWT) | Low priority for personal/small-team deployment. Add later. |

---

## 4. Domain Plugin System

### Directory Structure

```
domains/
├── _default/                    # Fallback domain (always loaded)
│   ├── manifest.yaml
│   ├── prompts/
│   │   ├── ontology.md
│   │   ├── persona.md
│   │   ├── report_guidelines.md
│   │   └── config_gen.md
│   └── ontology/
│       └── hints.yaml
│
├── example-social/              # Example: social media prediction
│   ├── manifest.yaml
│   ├── prompts/
│   │   ├── ontology.md
│   │   ├── persona.md
│   │   ├── report_guidelines.md
│   │   └── config_gen.md
│   ├── ontology/
│   │   └── hints.yaml
│   └── simulation/
│       └── platform_defaults.yaml
│
└── example-adtest/              # Example: ad copy testing
    ├── manifest.yaml
    └── prompts/
        └── ...
```

### manifest.yaml Schema

```yaml
name: example-social
version: "1.0"
description: "Social media prediction and narrative analysis"
language: en                     # Default language for prompts/reports
sim_engine: oasis                # oasis | claude
platforms: [twitter, reddit]
graph:
  default_backend: networkx
  vector_store: chromadb
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks: [Person, Organization]
```

### Domain Scaffolding

Three ways to create a domain:

1. **CLI interactive:** `forkcast domain create` — walks through configuration step by step
2. **API endpoint:** `POST /api/domains` — for future UI wizard
3. **LLM-assisted:** `forkcast domain create --from-description "Ad copy testing for B2B SaaS products targeting enterprise buyers"` — Claude generates the full domain structure from a natural language description

---

## 5. Data Layer

### SQLite Database (forkcast.db)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `projects` | Uploaded docs + ontology | id, domain, name, status, ontology_json, requirement, created_at |
| `project_files` | Uploaded file references | id, project_id, filename, path, text_content, size |
| `simulations` | Simulation instances | id, project_id, graph_id, status, engine_type, platforms, config_json |
| `simulation_actions` | Agent actions log | id, simulation_id, round, agent_id, action_type, content, platform, timestamp |
| `reports` | Generated reports | id, simulation_id, status, outline_json, content_markdown, created_at |
| `chat_history` | Interaction logs | id, report_id, role, message, tool_calls_json, timestamp |
| `token_usage` | Cost tracking | id, project_id, operation, input_tokens, output_tokens, model, timestamp |

### File Storage

```
data/
├── forkcast.db
├── {project_id}/
│   ├── uploads/           # Original uploaded files
│   ├── graph.json         # NetworkX serialized graph
│   ├── chroma/            # ChromaDB local persistence
│   ├── profiles/          # Generated agent profiles
│   └── simulation/        # Simulation working directory
│       ├── config.json
│       ├── actions.jsonl
│       └── ipc/
```

Structured queryable data lives in SQLite. Large serialized data (graphs, profiles, simulation artifacts) stays as files.

---

## 6. Graph Pipeline

### Ingestion Flow

```
Upload files
  → Extract text (PDF, MD, TXT)
  → Chunk text (configurable size/overlap)
  → For each chunk:
      Claude tool_use with domain ontology hints
      → Returns: entities[] + relationships[]
  → Deduplicate entities by name + type
  → Build NetworkX DiGraph
  → Embed text chunks + entity summaries → ChromaDB
  → Persist graph.json + chroma/
```

Entity extraction is synchronous via Claude tool_use — no async polling or waiting. The entire graph builds in one pass.

### Entity Extraction Tool Schema

```json
{
  "name": "extract_entities",
  "description": "Extract entities and relationships from text based on the provided ontology",
  "input_schema": {
    "type": "object",
    "properties": {
      "entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "type": {"type": "string"},
            "description": {"type": "string"},
            "attributes": {"type": "object"}
          }
        }
      },
      "relationships": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "source": {"type": "string"},
            "target": {"type": "string"},
            "type": {"type": "string"},
            "fact": {"type": "string"}
          }
        }
      }
    }
  }
}
```

### Search Capabilities

| Type | Implementation | Speed |
|------|---------------|-------|
| Semantic search | ChromaDB `collection.query()` | ~50ms |
| Graph traversal | NetworkX `G.neighbors()`, `G.edges()` | Instant |
| Hybrid | Semantic search → graph expansion | ~50ms |

### Graph Memory Updates During Simulation

Agent actions are converted to natural language, embedded into ChromaDB, and new edges/nodes added to the NetworkX graph. Batched (5 actions per update) to minimize overhead.

---

## 7. Simulation Engines

### Common Output Format

Both engines produce the same action format:

```json
{
  "round": 1,
  "timestamp": "2024-01-15T10:30:00Z",
  "agent_id": 3,
  "agent_name": "user3",
  "platform": "reddit",
  "action_type": "CREATE_POST",
  "action_args": {"content": "..."},
  "success": true
}
```

### OASIS Engine

- Runs as subprocess with file-based IPC
- Monitor thread reads `actions.jsonl`
- Profile formats: CSV (Twitter), JSON (Reddit)
- Process group isolation for clean termination
- Domain config can override platform defaults

### Claude Engine

- Runs in-process (no subprocess)
- For each round, for each active agent:
  - Send: system prompt (persona) + simulation context + recent activity
  - Claude returns: tool_use call (create_post, like_post, follow, etc.)
  - Action applied to in-memory simulation state
- Outputs same JSONL format as OASIS
- Sequential agent processing (vs OASIS parallel)
- Higher quality reasoning per agent, higher API cost

### Engine Selection

- Default set in domain `manifest.yaml`: `sim_engine: oasis`
- Overridable per simulation at creation time
- Both engines support dual-platform (Twitter + Reddit)

### Simulation Platforms

Dual Twitter + Reddit simulation supported. Future versions will add real-world data integration — ingesting actual Reddit/Twitter data to blend with simulated data in the analysis pipeline.

---

## 8. Claude API Integration

### Three Usage Modes

**Tool Use** (replaces hand-rolled ReACT):
- Entity extraction from text chunks
- Report generation with graph search + agent interview tools
- Chat interaction with tool access
- Domain scaffolding from natural language

**Extended Thinking** (replaces multi-step LLM chains):
- Simulation config generation (time + events + agents + platform in one coherent pass)
- Persona generation for richer, more consistent profiles

**Standard Completions:**
- Ontology generation via structured output
- Claude-as-simulator agent action decisions

### Client Wrapper

```
claude_client.py
  - tool_use(messages, tools, model) → tool results
  - think(messages, thinking_budget) → extended thinking response
  - complete(messages, model) → standard completion
  - All calls: automatic retry, token tracking, cost logging to SQLite
```

### Cost Awareness

- Token usage logged per project in SQLite `token_usage` table
- Domain config can set token budgets (soft limits with warnings)
- Claude-as-simulator shows per-round cost estimate before starting
- `forkcast usage` command shows cost summary

---

## 9. Report Pipeline

### Approach: Fully LLM-Driven

Claude decides report structure, sections, and narrative arc. Domain config provides guidelines (via `report_guidelines.md` prompt template) but does not enforce a fixed format.

### Tools Available to Report Agent

| Tool | Purpose |
|------|---------|
| `graph_search` | Semantic search across knowledge graph via ChromaDB |
| `graph_explore` | Traverse graph structure — neighbors, paths, clusters |
| `simulation_data` | Query simulation actions, stats, timelines |
| `interview_agent` | Ask a specific simulation agent a question |

### Generation Flow

```
1. Claude receives: simulation summary + domain report guidelines
2. Claude plans report structure (using extended thinking)
3. For each section:
   - Claude decides what data it needs
   - Calls tools (graph_search, interview_agent, etc.)
   - Synthesizes section content
4. Final report assembled as markdown
5. Streamed to client via SSE as sections complete
```

---

## 10. API Design

### Core Resources

| Resource | Key Endpoints |
|----------|--------------|
| Domains | `GET /api/domains`, `POST /api/domains` |
| Projects | `POST /api/projects` (upload + create), `GET /api/projects/{id}`, `POST /api/projects/{id}/build-graph` |
| Simulations | `POST /api/simulations` (create), `POST /api/simulations/{id}/prepare`, `POST /api/simulations/{id}/start`, `POST /api/simulations/{id}/stop` |
| Reports | `POST /api/reports/generate`, `GET /api/reports/{id}`, `GET /api/reports/{id}/export` |
| Chat | `POST /api/chat/report`, `POST /api/chat/agent` |
| System | `GET /health`, `GET /api/usage` |

### SSE Streams (Replace All Polling)

```
GET /api/projects/{id}/build-graph/stream
GET /api/simulations/{id}/prepare/stream
GET /api/simulations/{id}/run/stream
GET /api/reports/{id}/generate/stream
```

Each stream emits typed events:

```
event: progress
data: {"stage": "extracting", "current": 5, "total": 12}

event: action
data: {"round": 3, "agent": "user5", "type": "CREATE_POST", "content": "..."}

event: complete
data: {"result": {...}}

event: error
data: {"message": "..."}
```

### Response Envelope

```json
{"success": true, "data": {...}}
{"success": false, "error": "message"}
```

---

## 11. CLI Interface

```
forkcast domain list
forkcast domain create
forkcast domain create --from-description "..."

forkcast project create <files...> --domain <name> --prompt "..."
forkcast project list
forkcast project show <id>
forkcast project build-graph <id>

forkcast sim create <project_id> --engine oasis --platforms twitter,reddit
forkcast sim prepare <sim_id>
forkcast sim start <sim_id> --max-rounds 50
forkcast sim stop <sim_id>
forkcast sim show <sim_id>

forkcast report generate <sim_id>
forkcast report show <report_id>
forkcast report export <report_id> -o output.md

forkcast chat report <report_id>
forkcast chat agent <sim_id> <agent_id>

forkcast usage
forkcast server start
```

The CLI connects to a running ForkCast server or starts an embedded one. All streaming commands consume SSE endpoints and render progress in the terminal.

---

## 12. Build Phases

| Phase | Scope | Deliverables |
|-------|-------|-------------|
| **1. Foundation** | Project structure, SQLite models, Claude client wrapper, domain plugin loader, CLI skeleton, config from .env | Working `forkcast` CLI that can list domains and create projects |
| **2. Graph Pipeline** | Claude entity extraction, NetworkX graph storage, ChromaDB indexing, ontology generation, SSE streaming | `forkcast project create` + `build-graph` working end-to-end |
| **3. Simulation Prep** | Profile generation with Claude, config generation with extended thinking, domain-driven prompts | `forkcast sim create` + `prepare` working |
| **4. Simulation Engines** | OASIS subprocess runner, Claude-as-simulator, SSE action streaming, engine selection | `forkcast sim start` working with both engines |
| **5. Report + Chat** | Claude tool-use report agent, graph search tools, agent interview, chat endpoints | `forkcast report generate` + `chat` working |
| **6. First Domain** | Build a complete example domain plugin, validate end-to-end workflow | Full pipeline working with one domain |
| **7. UI** | Frontend consuming the API, built after backend is proven | Web interface for full workflow |

### Estimated Timeline: ~14-18 days (Claude Code assisted)

### Assumptions

- Claude Code handles boilerplate and routine implementation
- Human decisions focus on UX, prompt tuning, and architecture trade-offs
- OASIS kept as-is for subprocess integration
- Dual-platform simulation (Twitter + Reddit)
- Single-user/small-team deployment

---

## 13. Legal: Clean-Room Implementation

ForkCast is an original product. It is inspired by the general concept of agent-based collective intelligence prediction, which is a well-established research area. The implementation is entirely original:

- All code written from scratch — no code copied or adapted from any AGPL or restrictively-licensed codebase
- All prompts written fresh — no porting of existing prompt templates
- Original API design, data models, and internal architecture
- Original CLI interface and domain plugin system
- The concept of "simulate agent interactions to generate predictions" is not proprietary — it is established in academic literature on agent-based modeling, computational social science, and multi-agent simulation

No dependency on or derivation from any AGPL-licensed software. ForkCast's license will be chosen independently.
