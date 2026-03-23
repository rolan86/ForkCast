# Phase 7b UI Bugs

Discovered during manual UI testing on 2026-03-23 after Phase 7b merge.

---

## Bug 1: Completed simulations table breaks on platforms field
- **Where:** `frontend/src/views/SimulationTab.vue:361`
- **Symptom:** Completed simulations table doesn't render properly
- **Root cause:** `JSON.parse(sim.platforms || '[]')` is called on data that's already an array — backend `list_simulations` (simulation_routes.py:115) parses it before returning. `JSON.parse` on an array object errors.
- **Fix:** Remove `JSON.parse`, use `sim.platforms` directly
- **Status:** [ ] Open

## Bug 2: No `created` status handling in state machine
- **Where:** `frontend/src/views/SimulationTab.vue:46-63`
- **Symptom:** A simulation in `created` status (configured but not prepared) falls through to the `else` branch and shows the "completed" view
- **Root cause:** `onMounted` status routing only handles `preparing`, `prepared`, `running`, then falls through to `completed` for everything else — including `created` and `failed`.
- **Fix:** Add explicit `created` branch that shows settings panel with prepare button
- **Status:** [ ] Open

## Bug 3: Configuration panel shows immediately on Simulations tab (for prepared sims)
- **Where:** `frontend/src/views/SimulationTab.vue:55-56`
- **Symptom:** Clicking the Simulations tab immediately shows SimulationSettings + config without context
- **Root cause:** If latest simulation is `prepared`, `loadPreparedState()` runs on mount, rendering settings and config. No header/context tells the user *which* simulation they're looking at.
- **Fix:** Add simulation header showing which sim is loaded (ID, date, status) so the prepared view has context
- **Status:** [ ] Open

## Bug 4: Navigating away during prepare loses SSE connection — shows empty state on return
- **Where:** `frontend/src/views/SimulationTab.vue:66-68` (onUnmounted), `44-63` (onMounted)
- **Symptom:** Click Prepare → switch to Graph tab → switch back → see "create simulation" empty state, leading to duplicate simulation creation
- **Root cause:** (1) `onUnmounted` closes the SSE connection. (2) On return, `onMounted` re-runs and fetches simulations. (3) The `preparing` status is only tracked in-memory via `_prepare_queues` in the API — never persisted to DB. The simulation status in DB is still `created`. (4) Falls through to wrong view (Bug 2).
- **Fix:** Write `status = 'preparing'` to DB when prepare starts. On re-mount, detect `preparing` status and reconnect SSE (or show "preparation in progress" with reconnect).
- **Status:** [ ] Open

## Bug 5: OASIS shows disabled but engine dropdown shows OASIS selected
- **Where:** `frontend/src/api/simulations.js:7`, `frontend/src/components/SimulationSettings.vue:16`
- **Symptom:** Engine toggle shows OASIS as the active selection but with disabled/dimmed styling
- **Root cause:** `createSimulation()` in `simulations.js:7` hardcodes default `engine_type` to `'oasis'`. New simulations are created with `engine_type = 'oasis'`, then `SimulationSettings` picks it up from the DB. But OASIS isn't installed, so the button appears selected + dimmed.
- **Fix:** Change frontend default from `'oasis'` to `'claude'` in `simulations.js`. Or better: don't send engine_type at all and let backend use domain defaults.
- **Status:** [ ] Open

## Bug 6: No guidance on how to install OASIS
- **Where:** `frontend/src/components/SimulationSettings.vue:90`
- **Symptom:** OASIS button says "camel-oasis not installed" but offers no install guidance
- **Root cause:** Tooltip only says "not installed". No link or instructions. OASIS installs via `uv add camel-oasis`.
- **Fix:** Expand tooltip to include install command, or hide OASIS option entirely when unavailable.
- **Status:** [ ] Open

## Bug 7: No simulation selector — can't navigate between simulations
- **Where:** `frontend/src/views/SimulationTab.vue:347-389`
- **Symptom:** Completed view shows a table of all sims, but clicking a row only toggles an expand panel — can't navigate into a specific simulation's details, re-run it, or view its actions
- **Root cause:** The expand panel only has a disabled "Generate Report" button. No way to select a different simulation.
- **Fix:** Either make rows clickable to load that simulation's state, or add view/re-run buttons in the expand panel.
- **Status:** [ ] Open
