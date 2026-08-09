# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ForkCast is a collective intelligence simulation platform. It takes seed documents and a prediction question, builds a knowledge graph, generates AI agent personas, runs multi-round social media simulations (Twitter/Reddit-like), and produces analytical reports. Dual interfaces: FastAPI REST API + Typer CLI. Vue 3 frontend optional.

## Development Commands

### Backend (Python — managed with `uv`)

```bash
# Install (editable)
pip install -e .

# Run API server (default: localhost:5001)
forkcast server start
forkcast server start --reload   # with hot-reload

# Run all tests
pytest

# Run a single test file
pytest tests/test_graph_store.py

# Run a single test by name
pytest tests/test_graph_store.py -k "test_save_and_load"

# Tests use asyncio_mode = "auto" — async tests just work
```

### Frontend (Vue 3 — managed with `npm`)

```bash
cd frontend
npm install
npm run dev      # Vite dev server on localhost:5173, proxies /api → localhost:5001
npm run build    # Production build to frontend/dist/
```

Both servers must be running for full-stack development: backend on :5001, frontend on :5173.

## Architecture

### Pipeline Stages

Documents → **Graph Building** (extract → chunk → ontology → entities → graph + vectors) → **Preparation** (graph entities → persona generation → simulation config) → **Simulation** (multi-round agent action loop) → **Report** (tool-use research loop → analysis) → **Evaluation** (16 programmatic gates + 7 LLM judgments → scorecard)

### Backend (`src/forkcast/`)

- **`config.py`** — Frozen `Settings` dataclass singleton from env vars. All paths resolve from `_PROJECT_ROOT`.
- **`db/`** — SQLite with WAL mode. Schema has migration path v1→v4. `connection.py` handles init + migration, `queries.py` has shared helpers.
- **`llm/client.py`** — `ClaudeClient` wraps Anthropic SDK with 5 patterns: `complete()`, `tool_use()`, `think()` (extended reasoning), `stream()`, `smart_call()` (auto-dispatch). Exponential backoff retry on rate limits.
- **`graph/`** — Knowledge graph pipeline. `pipeline.py` orchestrates: text extraction → chunking (1000 chars, 200 overlap) → LLM ontology → tool-use entity extraction → NetworkX graph + ChromaDB vectors.
- **`simulation/`** — Two engines: `claude_engine.py` (native tool-use, 7 action tools) and `oasis_engine.py` (optional camel-oasis). `runner.py` selects engine, manages rounds, checkpoints for resume. `state.py` tracks feeds/posts/followers/mutes.
- **`report/`** — Tool-use loop: 5 research tools (graph_search, graph_explore, simulation_data, interview_agent, agent_actions) feed an LLM analyst that writes markdown reports.
- **`eval/`** — Two-layer evaluation: `gates.py` (16 programmatic checks), `judgments.py` (7 LLM rubric-based scores). Rubric templates in `rubrics/`.
- **`domains/`** — File-based plugin system. Each domain has `manifest.yaml` + `prompts/` (Jinja2 templates) + `ontology/hints.yaml`. Resolution: domain-specific → `_default` fallback.
- **`api/`** — FastAPI app factory in `app.py`. Routes: projects, graphs, simulations, reports, domains, capabilities. SSE streaming for long-running operations.
- **`cli/`** — Typer subcommands mirror API: `project`, `sim`, `report`, `chat`, `eval`, `domain`, `server`.

### Frontend (`frontend/src/`)

- **Vue 3 + Pinia + Vue Router + Tailwind CSS v4 + D3.js**
- **`stores/project.js`** — Central Pinia store managing projects, graphs, simulations, SSE progress state.
- **`api/`** — Fetch-based API client modules matching backend routes.
- **`views/`** — `ProjectListView` (dashboard), `ProjectWizard` (3-step creation), `ProjectLayout` (tab container with Overview/Graph/Simulation/Report tabs).
- **`components/graph/`** — D3 graph visualization with multiple layout algorithms (force, hierarchical, circular), hybrid Canvas+SVG rendering, and minimap.
- **`composables/useGraphState.js`** — Graph UI state management (layout, selection, view modes).
- **Path alias:** `@` → `frontend/src/`

### Domain Plugin Structure

```
domains/{name}/
├── manifest.yaml          # name, sim_engine, platforms, prompt paths
├── prompts/               # Jinja2 templates (ontology, persona, config_gen, agent_system, report_guidelines)
└── ontology/hints.yaml    # Seed entity types for the LLM
```

Resolution order: domain-specific file → `_default` → error.

## Key Patterns

- **ID prefixes:** Projects use `proj_`, simulations use `sim_`, reports use `report_` + hex suffixes.
- **SSE streaming:** Long-running operations (graph build, simulation, report) stream progress via SSE endpoints.
- **Test fixtures:** `conftest.py` provides `tmp_data_dir`, `tmp_db_path`, `tmp_domains_dir` (with minimal `_default` domain), and `mock_anthropic`. Tests use temp directories — never touch `data/`.
- **Settings override in tests:** Use `reset_settings()` + env var patching to isolate test config.
- **API response format:** All endpoints use `success()` / `error()` helpers from `api/responses.py`.
- **Simulation resume:** Both engines support checkpoint/resume via serialized state.

## Environment

Required: `ANTHROPIC_API_KEY` in `.env`. Optional overrides: `FORKCAST_DATA_DIR`, `FORKCAST_PORT` (default 5001), `FORKCAST_LOG_LEVEL`, etc. See `.env.example`.
