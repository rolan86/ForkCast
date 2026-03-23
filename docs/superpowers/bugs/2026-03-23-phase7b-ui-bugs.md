# Phase 7b UI Bugs

Discovered during manual UI testing on 2026-03-23 after Phase 7b merge.

---

## Bug 1: Completed simulations table breaks on platforms field
- **Where:** `frontend/src/views/SimulationTab.vue:361`
- **Symptom:** Completed simulations table doesn't render properly
- **Root cause:** `JSON.parse(sim.platforms || '[]')` is called on data that's already an array — backend `list_simulations` (simulation_routes.py:115) parses it before returning. `JSON.parse` on an array object errors.
- **Fix:** Use `Array.isArray(sim.platforms) ? sim.platforms : []` instead
- **Status:** [x] Fixed

## Bug 2: No `created` status handling in state machine
- **Where:** `frontend/src/views/SimulationTab.vue:46-63`
- **Symptom:** A simulation in `created` status (configured but not prepared) falls through to the `else` branch and shows the "completed" view
- **Root cause:** `onMounted` status routing only handles `preparing`, `prepared`, `running`, then falls through to `completed` for everything else — including `created` and `failed`.
- **Fix:** Added explicit `created`/`failed` branch with settings panel + prepare button. New `prepareExisting()` function prepares without creating a new simulation.
- **Status:** [x] Fixed

## Bug 3: Configuration panel shows immediately on Simulations tab (for prepared sims)
- **Where:** `frontend/src/views/SimulationTab.vue:55-56`
- **Symptom:** Clicking the Simulations tab immediately shows SimulationSettings + config without context
- **Root cause:** If latest simulation is `prepared`, `loadPreparedState()` runs on mount, rendering settings and config. No header/context tells the user *which* simulation they're looking at.
- **Fix:** Added simulation header with ID fragment, description, and status badge to both `created` and `prepared` views.
- **Status:** [x] Fixed

## Bug 4: Navigating away during prepare loses SSE connection — shows empty state on return
- **Where:** `frontend/src/views/SimulationTab.vue:66-68` (onUnmounted), `44-63` (onMounted)
- **Symptom:** Click Prepare → switch to Graph tab → switch back → see "create simulation" empty state, leading to duplicate simulation creation
- **Root cause:** (1) `onUnmounted` closes the SSE connection. (2) On return, `onMounted` re-runs and fetches simulations. (3) The `preparing` status was only tracked in-memory via `_prepare_queues` in the API — never persisted to DB. The simulation status in DB was still `created`. (4) Falls through to wrong view (Bug 2).
- **Fix:** Backend now writes `status = 'preparing'` to DB when prepare starts, and `status = 'failed'` if prepare errors. Frontend `onMounted` detects `preparing` status and reconnects SSE.
- **Status:** [x] Fixed

## Bug 5: OASIS shows disabled but engine dropdown shows OASIS selected
- **Where:** `frontend/src/api/simulations.js:7`, `frontend/src/components/SimulationSettings.vue:16`
- **Symptom:** Engine toggle shows OASIS as the active selection but with disabled/dimmed styling
- **Root cause:** `createSimulation()` in `simulations.js:7` hardcoded default `engine_type` to `'oasis'`. New simulations were created with `engine_type = 'oasis'`, then `SimulationSettings` picked it up from the DB. But OASIS isn't installed, so the button appeared selected + dimmed.
- **Fix:** Frontend `createSimulation()` no longer sends engine_type/platforms by default — lets backend use domain manifest defaults (which default to `'claude'`).
- **Status:** [x] Fixed

## Bug 6: No guidance on how to install OASIS
- **Where:** `frontend/src/components/SimulationSettings.vue:90`
- **Symptom:** OASIS button says "camel-oasis not installed" but offers no install guidance
- **Root cause:** Tooltip only says "not installed". No link or instructions. OASIS installs via `uv add camel-oasis`.
- **Fix:** Tooltip now shows: "Not available — install with: uv add camel-oasis"
- **Status:** [x] Fixed

## Bug 7: No simulation selector — can't navigate between simulations
- **Where:** `frontend/src/views/SimulationTab.vue:347-389`
- **Symptom:** Completed view shows a table of all sims, but clicking a row only toggles an expand panel — can't navigate into a specific simulation's details, re-run it, or view its actions
- **Root cause:** The expand panel only had a disabled "Generate Report" button. No way to select a different simulation.
- **Fix:** Added context-aware action buttons in expand panel: "Run" for prepared sims, "View Actions" for completed sims, "Configure" for created/failed sims.
- **Status:** [x] Fixed

---

## Bug 8: SSE JSON parse errors crash the message handler
- **Where:** `frontend/src/lib/sse.js:41-46`
- **Symptom:** If backend sends malformed SSE data, `JSON.parse` throws and the entire handler crashes silently
- **Root cause:** No try-catch around `JSON.parse(event.data)` in the stage event listener
- **Fix:** Wrapped in try-catch with `console.warn` — malformed events are logged and skipped
- **Status:** [x] Fixed

## Bug 9: Double-click or rapid navigation creates multiple SSE connections
- **Where:** `frontend/src/views/SimulationTab.vue` — prepareSimulation, prepareExisting, startSimulation
- **Symptom:** Clicking "Prepare" twice rapidly, or navigating away and back, opens duplicate SSE connections causing duplicate progress events
- **Root cause:** No guard against concurrent invocations. Each call to `prepareSimulation`/`startSimulation` opens a new SSE without closing the previous one reliably.
- **Fix:** Added `busy` ref guard on all SSE-initiating functions + `closePreviousSSE()` helper called before opening new connections
- **Status:** [x] Fixed

## Bug 10: SSE reconnection doesn't clear "Connection lost" error
- **Where:** `frontend/src/lib/sse.js:72-82`, `frontend/src/views/SimulationTab.vue:133-136,179-182`
- **Symptom:** After a temporary network blip, SSE reconnects and data flows again, but the "Connection lost" error message stays visible
- **Root cause:** `onerror` sets `prepareError`/`runError = 'Connection lost'` via `onDisconnect`, but successful reconnection never clears it
- **Fix:** Added `wasDisconnected` flag in `sse.js` set on error, cleared on first successful message post-reconnect which triggers `onReconnect` callback. SimulationTab handlers clear error refs in `onReconnect`.
- **Status:** [x] Fixed

---

## Audit: Additional Bugs (identified 2026-03-23)

### High Severity

## Bug 11: Capabilities store not loaded before SimulationSettings renders
- **Where:** `frontend/src/components/SimulationSettings.vue:14`, `frontend/src/stores/capabilities.js`
- **Symptom:** Model dropdowns may be empty if capabilities haven't been fetched yet
- **Root cause:** SimulationSettings uses `caps.models` immediately but doesn't trigger `fetchCapabilities()` — relies on parent having called it
- **Status:** [ ] Open

## Bug 12: Store state not reset between simulations
- **Where:** `frontend/src/stores/project.js`
- **Symptom:** Switching between simulations may show stale progress/actions from previous simulation
- **Root cause:** `simPrepareProgress`, `simRunProgress`, `liveFeedActions` are global store state not scoped to a simulation ID
- **Status:** [ ] Open

## Bug 13: API error response shape not validated
- **Where:** `frontend/src/api/simulations.js`
- **Symptom:** If backend returns unexpected error shape, frontend may show `undefined` as error message
- **Root cause:** API functions assume `resp.data.message` exists on error responses without validation
- **Status:** [ ] Open

## Bug 14: Graph rebuild doesn't warn about dependent simulations
- **Where:** `frontend/src/views/GraphTab.vue`
- **Symptom:** Rebuilding graph silently invalidates all existing simulations that reference the old graph
- **Root cause:** No check for simulations referencing current graph before allowing rebuild
- **Status:** [ ] Open

### Medium Severity

## Bug 15: No loading indicator when fetching simulation details
- **Where:** `frontend/src/views/SimulationTab.vue:139-146`
- **Symptom:** `loadPreparedState` makes an API call but shows no loading indicator — UI appears frozen
- **Status:** [ ] Open

## Bug 16: Completed view doesn't show actions_count or rounds from DB
- **Where:** `frontend/src/views/SimulationTab.vue:468-469`
- **Symptom:** Table shows `?` for rounds and `-` for actions because fields aren't populated
- **Root cause:** Backend `list_simulations` doesn't include `rounds_completed`, `total_rounds`, or `actions_count` in the query
- **Status:** [ ] Open

## Bug 17: `showAllAgents` state persists across simulation switches
- **Where:** `frontend/src/views/SimulationTab.vue:27,337`
- **Symptom:** If "Show all agents" was expanded for one sim, it stays expanded for the next
- **Root cause:** `showAllAgents` ref is never reset when simulation changes
- **Status:** [ ] Open

## Bug 18: SimulationConfigView receives null config gracefully but shows empty
- **Where:** `frontend/src/components/SimulationConfigView.vue`
- **Symptom:** When config is null/undefined, the component renders but shows nothing — no "not yet generated" message
- **Status:** [ ] Open

## Bug 19: Stop simulation has no error handling
- **Where:** `frontend/src/views/SimulationTab.vue:185-188`
- **Symptom:** If stop API fails, error is swallowed silently
- **Root cause:** `stopSimulation()` doesn't catch errors
- **Status:** [ ] Open

### Low Severity

## Bug 20: Expand panel in completed table lacks keyboard accessibility
- **Where:** `frontend/src/views/SimulationTab.vue:456-461`
- **Symptom:** Row click handler only works with mouse — no keyboard focus or Enter/Space handling
- **Status:** [ ] Open

## Bug 21: No confirmation before re-prepare
- **Where:** `frontend/src/views/SimulationTab.vue:363`
- **Symptom:** "Re-prepare" button triggers immediately without warning that it will regenerate profiles
- **Status:** [ ] Open

## Bug 22: `viewActions` function is incomplete
- **Where:** `frontend/src/views/SimulationTab.vue:204-209`
- **Symptom:** Clicking "View Actions" sets viewState to completed but doesn't load the actions
- **Root cause:** TODO comment — function only sets state, doesn't fetch or display actions
- **Status:** [ ] Open
