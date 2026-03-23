# ForkCast Testing Guide

How to test the ForkCast application end-to-end — backend API, frontend UI, and their integration.

## Prerequisites

1. **Python 3.11+** with `uv` installed
2. **Node.js 18+** with `npm`
3. **Anthropic API key** (for graph building and simulations)

```bash
# Clone and install backend dependencies
cd ForkCast
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Set up environment
cp .env.example .env
# Edit .env → set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Part 1: Automated Tests (No API Key Required)

Run the full test suite — 412 tests covering all backend logic, API endpoints, SSE streaming, frontend build output, frontend-backend contract verification, simulation settings, checkpoint/resume, and error classification.

```bash
uv run pytest -q
```

**Expected output:**
```
412 passed in ~15s
```

To run the e2e integration tests:

```bash
uv run pytest tests/test_e2e_phase7a.py tests/test_e2e_phase7b.py -v
```

**Expected output:**
```
tests/test_e2e_phase7a.py::TestFullPipelineE2E::test_project_creation_and_listing PASSED
tests/test_e2e_phase7a.py::TestFullPipelineE2E::test_graph_build_and_data_endpoint PASSED
tests/test_e2e_phase7a.py::TestFullPipelineE2E::test_simulation_lifecycle PASSED
tests/test_e2e_phase7a.py::TestFullPipelineE2E::test_graph_data_404_without_graph PASSED
tests/test_e2e_phase7a.py::TestCORSConfiguration::test_cors_allows_frontend_origin PASSED
tests/test_e2e_phase7a.py::TestCORSConfiguration::test_cors_headers_on_get PASSED
tests/test_e2e_phase7a.py::TestAPIEnvelopeConsistency::test_success_envelope PASSED
tests/test_e2e_phase7a.py::TestAPIEnvelopeConsistency::test_error_envelope_404 PASSED
tests/test_e2e_phase7a.py::TestAPIEnvelopeConsistency::test_domains_endpoint PASSED
tests/test_e2e_phase7a.py::TestSSEEndpoints::test_graph_build_stream_content_type PASSED
tests/test_e2e_phase7a.py::TestSSEEndpoints::test_simulation_prepare_stream_content_type PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_index_html_exists PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_index_html_references_assets PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_has_js_bundles PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_has_css_bundle PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_vue_router_routes_in_bundle PASSED
tests/test_e2e_phase7a.py::TestFrontendBuild::test_dist_lazy_chunks_exist PASSED
tests/test_e2e_phase7a.py::TestFrontendBackendContract::test_project_response_has_frontend_required_fields PASSED
tests/test_e2e_phase7a.py::TestFrontendBackendContract::test_graph_data_response_has_d3_fields PASSED
tests/test_e2e_phase7a.py::TestFrontendBackendContract::test_simulation_response_has_frontend_required_fields PASSED
tests/test_e2e_phase7a.py::TestFrontendBackendContract::test_graph_metadata_has_frontend_required_fields PASSED
tests/test_e2e_phase7a.py::TestFrontendBackendContract::test_domains_response_has_frontend_required_fields PASSED

28 passed in ~3s
```

Phase 7b-specific tests can be run individually:

```bash
# Simulation settings (engine, platforms, model selection)
uv run pytest tests/test_simulation_settings.py -v

# smart_call() dispatch (model routing to think/complete)
uv run pytest tests/test_smart_call.py -v

# Profile reuse across simulations
uv run pytest tests/test_profile_reuse.py -v

# Checkpoint system and run resume
uv run pytest tests/test_run_resume.py -v

# Error classification
uv run pytest tests/test_error_classification.py -v

# Prepare pipeline (model selection + profile reuse wiring)
uv run pytest tests/test_prepare_resume.py -v

# SimulationState serialization (to_dict/from_dict)
uv run pytest tests/test_state_serialization.py -v

# Capabilities API endpoint
uv run pytest tests/test_api_capabilities.py -v
```

**Note:** The `TestFrontendBuild` tests require a prior `npm run build` in `frontend/`. If they fail, run:

```bash
cd frontend && npm run build && cd ..
```

---

## Part 2: Manual Testing (API Key Required)

### Step 1: Start the backend

```bash
uv run forkcast server start --port 8000
```

**Expected output:**
```
Starting ForkCast server on 127.0.0.1:8000
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Step 2: Verify backend health

In a new terminal:

```bash
curl http://localhost:8000/health | python -m json.tool
```

**Expected output:**
```json
{
    "success": true,
    "data": {
        "status": "ok",
        "version": "0.7.0"
    }
}
```

### Step 3: Start the frontend dev server

In a second terminal:

```bash
cd frontend
npm run dev
```

**Expected output:**
```
  VITE v6.x.x  ready in ~500ms

  ➜  Local:   http://localhost:5173/
```

The Vite dev server proxies `/api` and `/health` requests to `http://localhost:8000` automatically.

### Step 4: Open the app

Open **http://localhost:5173** in your browser.

**Expected:** The ForkCast UI loads with:
- A narrow icon rail on the left (logo "F", Projects button, theme toggle)
- The main area shows the **Project List** view
- If no projects exist, an empty state with a "New Project" button

### Step 5: Create a project

1. Click **"New Project"** (or go to http://localhost:5173/projects/new)
2. **Step 1 — Define:** Fill in project name and prediction requirement
   - Example name: `AI Regulation Test`
   - Example requirement: `Predict how major tech companies will respond to the EU AI Act in the next 12 months`
3. **Step 2 — Upload:** Drag & drop a text or PDF file with seed material
4. **Step 3 — Review:** Confirm details and submit

**Expected:** Redirected to the project detail page (Overview tab)

### Step 6: Build the knowledge graph

1. Click the **"Graph"** tab
2. Click **"Build Graph"**

**Expected:**
- A progress panel appears showing SSE-streamed build stages:
  - `chunking` — splitting documents into chunks
  - `ontology` — generating entity extraction ontology
  - `extraction` — extracting entities and relationships from chunks
  - `assembly` — building the NetworkX graph
- On first run, you'll see HuggingFace model download messages (sentence-transformers) — this is normal
- When complete, a D3 force-directed graph renders with nodes (entities) and edges (relationships)
- You can zoom, pan, click nodes for detail, search, and filter by type

### Step 7: Verify graph data via API

```bash
# Replace YOUR_PROJECT_ID with the actual ID from the URL bar
curl http://localhost:8000/api/projects/YOUR_PROJECT_ID/graph/data | python -m json.tool
```

**Expected output** (truncated):
```json
{
    "success": true,
    "data": {
        "nodes": [
            {"id": "EU AI Act", "type": "Concept", "description": "..."},
            {"id": "Google", "type": "Organization", "description": "..."}
        ],
        "edges": [
            {"source": "Google", "target": "EU AI Act", "label": "subject_to"}
        ]
    }
}
```

### Step 8: Check capabilities

```bash
curl http://localhost:8000/api/capabilities | python -m json.tool
```

**Expected output:**
```json
{
    "success": true,
    "data": {
        "engines": ["claude", "oasis"],
        "oasis_available": false,
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "supports_thinking": true},
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "supports_thinking": false}
        ]
    }
}
```

### Step 9: Create and configure a simulation

1. Click the **"Simulations"** tab
2. Click **"New Simulation"**
3. Before preparing, configure settings in the **Settings panel**:
   - **Engine**: Select "Claude" or "OASIS" (OASIS only available if installed)
   - **Platforms**: Toggle Twitter/Reddit on or off
   - **Prep Model**: Select model for profile/config generation (e.g., Haiku for speed)
   - **Run Model**: Select model for simulation execution
   - **Profile Reuse**: Toggle on to reuse profiles from prior simulations with the same graph
4. Click **"Save Settings"**

**Expected:**
- Settings persist (verify via `GET /api/simulations/{id}`)
- Settings panel shows saved values on reload

### Step 10: Prepare the simulation

1. Click **"Prepare"** on the configured simulation

**Expected:**
- Progress panel shows SSE-streamed preparation stages (profile generation, config generation)
- If prep_model is set to Haiku, `smart_call()` routes to `complete()` (no extended thinking)
- If profile reuse is active and a prior simulation with the same graph exists, profiles are copied instantly
- When complete, the **Config View** panel shows generated simulation parameters (timing, hot topics, seed posts)
- Status changes to "prepared" with a "Run" button

### Step 11: Run the simulation

1. Click **"Run"** on the prepared simulation

**Expected:**
- Live feed panel shows real-time agent actions
- Platform badges (Twitter/Reddit) indicate which platform each action is on
- Agent avatars with deterministic gradient colors appear next to each action
- **Checkpoint files** are written after each round (`data/{sim_id}/checkpoint.json`)
- Clicking **"Stop"** halts the simulation gracefully after the current round

### Step 12: Verify checkpoint system (API)

While a simulation is running:

```bash
# Check checkpoint exists
cat data/{simulation_id}/checkpoint.json
```

**Expected:**
```json
{"last_completed_round": 3, "total_rounds": 96, "platform": "twitter", "platform_index": 0, "completed_platforms": []}
```

After completion, checkpoint files are automatically cleaned up.

### Step 13: Test profile reuse

1. Create a **second simulation** for the same project (same graph)
2. Prepare it

**Expected:**
- Profiles are copied from the first simulation (instant, no LLM calls)
- Progress shows "reused" indicator
- The profiles are identical (can verify by diffing `data/{sim1}/profiles/agents.json` and `data/{sim2}/profiles/agents.json`)

### Step 14: Test error handling in UI

If the API key is invalid or an LLM call fails during prepare:

**Expected:**
- ProgressPanel shows a color-coded error message
- If the error is resumable (e.g., rate limit), a "Resume" button appears
- If not resumable, a "Start Over" button appears

### Step 15: Toggle theme

Click the **sun/moon icon** at the bottom of the icon rail.

**Expected:** App toggles between light and dark themes.

---

## Troubleshooting

### `vite: command not found`

Frontend dependencies not installed. Run:

```bash
cd frontend && npm install
```

### 500 error on graph/data endpoint

If you see `KeyError: 'id'` in the server logs, you may be running an older version. Pull latest and restart:

```bash
git pull && uv run forkcast server start --port 8000
```

### HuggingFace model warnings

On first graph build, you'll see:

```
Warning: You are sending unauthenticated requests to the HF Hub.
BertModel LOAD REPORT ... embeddings.position_ids | UNEXPECTED
```

These are harmless. The sentence-transformers model loads correctly. Set `HF_TOKEN` in `.env` to suppress the rate limit warning.

### Frontend can't reach backend

The Vite dev server proxies `/api` to `http://localhost:8000`. Make sure:
- Backend is running on port **8000** (not the default 5001)
- Or update `frontend/vite.config.js` proxy target to match your backend port
