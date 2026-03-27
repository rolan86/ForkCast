<div align="center">

# ForkCast

**Collective intelligence simulation platform. Predict anything.**

Upload documents. Ask a question. AI agents simulate how stakeholders would actually react.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-412%20passing-brightgreen.svg)]()
[![Claude API](https://img.shields.io/badge/LLM-Claude%20API-orange.svg)](https://anthropic.com)

</div>

---

## What It Does

You have a question: *"How will customers react to this pricing change?"* or *"What happens if we publish this policy?"* or *"Which ad copy performs better?"*

ForkCast answers it by simulation, not guesswork.

1. **Upload seed materials** — market reports, policy drafts, competitor analyses, ad copy, anything
2. **Describe your prediction** — natural language, no special syntax
3. **ForkCast builds a knowledge graph** — extracts every entity, relationship, and tension from your documents
4. **AI agents take form** — distinct personas with opinions, biases, and communication styles, built from the actual stakeholders in your data
5. **They simulate social discourse** — posting, commenting, liking, following, muting, arguing across a Twitter/Reddit-like platform for dozens of rounds
6. **You get a prediction report** — written by an AI analyst that interviewed the simulated agents and cross-referenced the knowledge graph

The result: a prediction grounded in collective dynamics, not a single model's best guess.

---

## Use Cases

**Ad Copy A/B Testing** — Tested two ad directions for a productivity app. 12 agents, 223 actions across 96 rounds. ForkCast correctly identified which copy would generate broader reach and which would trap itself in an echo chamber. [Full case study →](docs/use-cases/ad-copy-ab-testing.md)

**Business Concept Validation** — Will customers, competitors, and regulators actually respond the way your pitch deck assumes? Simulate it.

**Policy Impact Prediction** — Drop a policy draft into ForkCast. Watch how affected communities, advocacy groups, and media react before you publish.

**Crisis Scenario Modeling** — Test your crisis response. See how it plays out in a simulated public forum before it plays out in the real one.

**Narrative Evolution Tracking** — Understand how a story shifts over time as different stakeholders amplify, distort, or redirect it.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/merryldmello/forkcast.git
cd forkcast
pip install -e .

# Configure (only need an Anthropic API key)
cp .env.example .env
# Edit .env → set ANTHROPIC_API_KEY

# Run the API server
forkcast server start
```

That's it. One API key. No Zep. No managed graph database. No external services.

### Try Your First Prediction

```bash
# Create a project
forkcast project create \
  --name "My First Prediction" \
  --requirement "How will enterprise CTOs react to a new open source monitoring tool?"

# Upload seed documents
# (via API: POST /api/projects with file uploads)

# Build knowledge graph
forkcast sim create <project-id>
forkcast sim prepare <sim-id>

# Run the simulation
forkcast sim start <sim-id>

# Generate the report
forkcast report generate <sim-id>
```

### Frontend (Optional)

```bash
cd frontend
npm install
npm run dev    # localhost:5173, proxies to API on :5001
```

Vue 3 dashboard with project wizard, D3 knowledge graph visualization, live simulation feed, and report viewer.

---

## Architecture

```
Documents + Prediction Question
        │
        ▼
┌─────────────────┐
│  Graph Building  │  Extract text → Chunk → LLM Ontology → Entity Extraction → NetworkX + ChromaDB
└────────┬────────┘
         ▼
┌─────────────────┐
│   Preparation    │  Graph entities → Persona generation (extended thinking) → Simulation config
└────────┬────────┘
         ▼
┌─────────────────┐
│   Simulation     │  Multi-round agent loop: post, comment, like, follow, mute, do-nothing
└────────┬────────┘
         ▼
┌─────────────────┐
│     Report       │  Tool-use research loop (5 tools) → Structured analysis
└────────┬────────┘
         ▼
┌─────────────────┐
│   Evaluation     │  16 programmatic gates + 7 LLM quality judgments → Scorecard
└─────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| API | FastAPI + SSE streaming |
| Frontend | Vue 3, Pinia, Tailwind CSS, D3.js |
| CLI | Typer |
| Database | SQLite (WAL mode) |
| LLM | Anthropic Claude API (claude-sonnet-4-6) |
| Knowledge Graph | NetworkX (DiGraph) |
| Vector Store | ChromaDB (all-MiniLM-L6-v2) |
| Simulation Engines | Claude (native tool-use) + OASIS (optional) |
| Templates | Jinja2 |

---

## Why ForkCast?

This project was inspired by [MiroFish](https://github.com/666ghj/MiroFish), which proved the concept: swarm intelligence prediction works. 33,000 stars. Brilliant project.

ForkCast takes a different approach:

| | MiroFish | ForkCast |
|---|---|---|
| **LLM** | Qwen (Alibaba) via OpenAI SDK | Claude (Anthropic) native |
| **Simulation** | OASIS only | Dual: Claude tool-use + OASIS |
| **Domains** | Hardcoded | File-based plugin system |
| **Evaluation** | None | 16 gates + 7 LLM judgments |
| **Report Agent** | Basic | Tool-use loop with 5 research tools |
| **Agent Chat** | Limited | Full in-character conversations |
| **Dependencies** | Zep Cloud + LLM API | One API key. That's it. |
| **Language** | Chinese-first | English-first |

---

## Domain Plugin System

ForkCast is designed to predict anything, not just one category. Each prediction vertical is a **domain plugin**: a folder with a manifest and Jinja2 prompt templates.

```
domains/social-media/
├── manifest.yaml          # Name, engine, platforms, prompt paths
├── prompts/
│   ├── ontology.md        # How to extract entities from this domain
│   ├── persona.md         # How to generate realistic agent profiles
│   ├── config_gen.md      # Simulation parameter generation
│   ├── agent_system.md    # Agent behavior during simulation
│   └── report_guidelines.md  # Report structure and analysis style
└── ontology/
    └── hints.yaml         # Seed entity types for the LLM
```

**Shipped domains:** `_default` (generic), `social-media` (Twitter-native personas and social analyst reports)

**Build your own:** `forkcast domain create my-domain` scaffolds the full structure. Customize the prompts. Run a prediction.

---

## Evaluation Framework

Most AI projects have no way to tell you when their output is garbage. ForkCast does.

**Layer 1 — 16 Programmatic Gates** (fast, free, pass/fail):
Ontology structure, persona count, persona field validation, simulation action counts, report length, report structure, and more. All gates must pass before Layer 2 runs.

**Layer 2 — 7 LLM Quality Judgments** (rubric-based, 1-5 scoring):
Ontology specificity, persona distinctiveness, persona authenticity, simulation in-character behavior, interaction quality, report specialist quality, report evidence grounding.

```bash
# Run evaluation
forkcast eval run <sim-id>

# Compare two runs (before/after prompt tuning)
forkcast eval compare <scorecard-1> <scorecard-2>
```

The eval framework tells you exactly what's weak and how to fix it. Persona distinctiveness score low? The justification text explains why and what to change in the persona prompt.

---

## CLI Reference

```bash
# Projects
forkcast project create --name "..." --requirement "..."
forkcast project list
forkcast project get <id>
forkcast project delete <id>

# Simulations
forkcast sim create <project-id>
forkcast sim prepare <sim-id>
forkcast sim run <sim-id>
forkcast sim list
forkcast sim actions <sim-id>

# Reports
forkcast report generate <sim-id>
forkcast report list
forkcast report get <id>
forkcast report export <id>

# Chat
forkcast chat report <report-id>     # Q&A with the report agent
forkcast chat agent <sim-id> <name>  # Talk to any simulated agent in-character

# Evaluation
forkcast eval run <sim-id>
forkcast eval compare <id-1> <id-2>

# Domains
forkcast domain list
forkcast domain create <name>

# Server
forkcast server start
forkcast server start --reload
```

---

## REST API

All operations available via HTTP. Long-running operations stream progress via SSE.

| Endpoint | Description |
|----------|-------------|
| `POST /api/projects` | Create project with file uploads |
| `POST /api/projects/{id}/build-graph` | Build knowledge graph (SSE) |
| `POST /api/simulations` | Create simulation |
| `POST /api/simulations/{id}/prepare` | Generate personas + config |
| `POST /api/simulations/{id}/start` | Run simulation (SSE) |
| `POST /api/reports/generate` | Generate report (SSE) |
| `POST /api/reports/{id}/chat` | Chat with report agent |
| `GET /api/domains` | List available domains |
| `GET /api/capabilities` | Models, engines, agent modes |

Full API docs at `http://localhost:5001/docs` when running.

---

## Development

```bash
# Install with dev dependencies
pip install -e .
uv sync --group dev

# Run tests
pytest                          # All 412 tests
pytest tests/test_graph_store.py  # Single file
pytest -k "test_save_and_load"    # Single test

# Optional: Install OASIS engine
uv pip install --no-deps camel-oasis
```

### Project Structure

```
src/forkcast/
├── config.py          # Settings singleton (env vars)
├── db/                # SQLite with WAL, schema v1→v4
├── llm/               # ClaudeClient: complete, tool_use, think, stream
├── graph/             # Knowledge graph pipeline (extract → chunk → entities → graph)
├── simulation/        # Claude engine (tool-use) + OASIS engine + state management
├── report/            # Tool-use research loop + chat
├── eval/              # Gates + LLM judgments + rubrics
├── domains/           # Plugin loader + scaffolding
├── api/               # FastAPI routes + SSE
└── cli/               # Typer subcommands
```

60 source files. 65 test files. 412 tests passing.

---

## Requirements

- Python 3.11+
- Anthropic API key
- Node.js 18+ (for frontend, optional)

Optional: [OASIS](https://github.com/camel-ai/oasis) for the second simulation engine.

---

## License

[AGPL-3.0](LICENSE)

If you use ForkCast as a hosted service, you must release your source code under the same license. If you use it internally or for research, no obligation.

---

## Acknowledgments

ForkCast was inspired by [MiroFish](https://github.com/666ghj/MiroFish) by Guo Hangjiang. MiroFish proved that swarm intelligence prediction works at scale. ForkCast takes the concept in a different architectural direction.

The optional OASIS simulation engine is powered by [OASIS](https://github.com/camel-ai/oasis) from the CAMEL-AI team.
