# Graph UI Audit & Redesign — Design Spec

**Date:** 2026-03-26
**Author:** Claude
**Status:** Draft (v2 — post-review revision)
**Supersedes:** `2026-03-24-graph-ui-redesign-design.md` (v3)

## Problem Statement

The v3 graph UI redesign introduced clean component boundaries (GraphTopBar, GraphSettingsPanel) but left rendering logic in a 1,315-line GraphTab.vue. This has caused:

- **Critical bugs:** Layout switching from settings panel doesn't work (always renders force), render mode auto-selection overrides manual user choice
- **Broken features:** Mini-map viewport tracking doesn't update (plain `let` vars invisible to Vue), `_connCounts` not populated in hybrid mode breaking search highlighting
- **Visual inconsistency:** 3 components hardcode dark-theme colors ignoring the design token system, emoji icons where lucide is standard, scanline effects not in spec
- **UX gaps:** No color legend, sidebar animates from wrong direction, settings panel overlays entire viewport, rebuild button hidden when mini-map active, no affordances for interaction modes
- **Architecture debt:** Duplicate layout handlers, dead composable state, copy-pasted layout application code, direct mutation bypassing composable mutators

## Goals

1. **Extract rendering** from GraphTab.vue into a testable, reactive composable
2. **Fix all critical and high-severity bugs** identified in audit
3. **Unify the design system** — all graph components use CSS variables, lucide icons, no hardcoded colors
4. **Add missing UX affordances** — interaction mode indicators, color legend, selection actions
5. **Clean up dead code** — remove unused state, duplicate handlers, debug logging
6. **Rethink control placement** — frequently-used controls accessible without opening settings panel

## Non-Goals

- Changing the backend graph API
- Adding new layout algorithms
- Changing the graph data model
- Rewriting D3 rendering from scratch (we refactor, not replace)

## Design System Prerequisites

Before any component work begins, add these missing CSS variables to `main.css`:

```css
:root {
  /* Add to existing :root block */
  --surface-elevated: #f4f4f5;    /* Hover state surface (between raised and sunken) */
  --color-primary: #6366f1;       /* Primary action color — matches existing --accent */
  --color-primary-hover: #4f46e5; /* Matches existing --accent-hover */
}

.dark {
  /* Add to existing .dark block */
  --surface-elevated: #27272a;
  --color-primary: #818cf8;       /* Matches existing dark --accent */
  --color-primary-hover: #6366f1;
}
```

Also update `--graph-*` CSS variables to match `NEON_COLORS` from `constants/graph.js` (they currently diverge — e.g., Person is `#3b82f6` in CSS but `#00d4ff` in constants). NEON_COLORS is canonical; update the CSS vars to match.

**Note:** Several existing components already use `var(--surface-elevated)` and `var(--color-primary, #00d4ff)` with fallbacks. After adding these tokens, the fallback values in components should be removed to keep a single source of truth.

## Architecture

### Current State

```
GraphTab.vue (1,315 lines)
├── Data loading + SSE streaming
├── D3 rendering (hybrid + legacy) ← PROBLEM: 300+ lines of D3
├── 4 interaction modes (select/path/neighbor/lasso)
├── Layout switching (4 algorithms)
├── Search + filter logic
├── Zoom controls
├── Node selection + sidebar
├── Settings panel state
└── Mini-map navigation

useGraphState.js — UI state (layout, selection, view, clustering)
constants/graph.js — Colors, modes, thresholds
```

### Target State

```
GraphTab.vue (~400 lines) — View orchestration only
├── Data loading + SSE streaming
├── State coordination between composables and components
├── Search + filter delegation
└── Event handlers (thin wrappers)

useGraphRenderer.js (NEW) — All D3 rendering
├── Owns simulation, svgSelection, zoomBehavior, hybridRenderer
├── Exposes reactive refs: viewport, connCounts, isRendering
├── render(container, graphData, options)
├── applyLayout(type, nodes, edges, dimensions)
├── applySearchFilters(query, filters)
├── zoom controls (zoomIn, zoomOut, zoomReset, fitToScreen)
├── highlight helpers (path, neighbors, lasso)
└── destroy() cleanup

useGraphState.js — UI state (unchanged API, fix internals)
├── Remove dead layoutParams (or wire them to renderer)
├── Make graphState truly readonly via readonly()
├── Add interaction mode state with cursor/instruction metadata

constants/graph.js — Unchanged
```

### Component Tree Changes

```
KEEP (with fixes):
  GraphTopBar.vue        — Add color dots to filter buttons, add layout quick-switch dropdown
  GraphSettingsPanel.vue — Fix emit signatures, remove layout radios (moved to top bar)
  GraphErrorBoundary.vue — Unchanged

REWRITE (theme compliance):
  GraphStatsPanel.vue    — CSS variables instead of hardcoded dark, lucide icons instead of emoji
  GraphMiniMap.vue        — CSS variables, wire to reactive viewport from useGraphRenderer

INTEGRATE (currently unused):
  GraphLegend.vue         — Embed color association into GraphTopBar filter buttons
  GraphSelectionActions.vue — Floating toolbar when multi-select active

DELETE:
  GraphCanvas.vue         — Replaced by useGraphRenderer composable
  GraphLayoutControls.vue — Layout params will be wired through settings panel Advanced section
```

## Detailed Design

### 1. useGraphRenderer Composable

The core extraction. Owns all D3 state as reactive refs so Vue can track changes.

```javascript
// composables/useGraphRenderer.js

import { ref, shallowRef, readonly, onScopeDispose } from 'vue'

export function useGraphRenderer() {
  // Reactive state Vue can track
  const viewport = ref({ x: 0, y: 0, w: 0, h: 0 })
  const connCounts = ref({})
  const isRendering = ref(false)
  const renderMode = ref(null) // Tracks actual mode in use (may differ from user selection)

  // Internal D3 state (shallowRef so Vue tracks reference changes)
  const _svgSelection = shallowRef(null)
  const _zoomBehavior = shallowRef(null)
  const _hybridRenderer = shallowRef(null)
  const _simulation = shallowRef(null)
  const _container = shallowRef(null)
  let _resizeObserver = null

  /**
   * Bind the renderer to a DOM container.
   * Attaches ResizeObserver for automatic re-render on size change.
   * Must be called once (typically in onMounted).
   *
   * @param {HTMLElement} container - The DOM element to render into
   * @param {Function} onResize - Callback when container resizes (caller triggers re-render)
   */
  function bind(container, onResize) {
    _container.value = container
    _resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        onResize(entry.contentRect.width, entry.contentRect.height)
      }
    })
    _resizeObserver.observe(container)
  }

  /**
   * Get container dimensions, with fallback for initial render.
   * @returns {{ width: number, height: number }}
   */
  function getDimensions() {
    const container = _container.value
    if (!container) return { width: 800, height: 600 }
    return {
      width: container.clientWidth || 800,
      height: container.clientHeight || 600,
    }
  }

  /**
   * Build connection counts from edge data.
   * Called by render() BEFORE delegating to any render mode.
   * This ensures connCounts is available for both hybrid and legacy rendering.
   */
  function _buildConnCounts(edges) {
    const counts = {}
    edges.forEach(e => {
      const src = e.source.id || e.source
      const tgt = e.target.id || e.target
      counts[src] = (counts[src] || 0) + 1
      counts[tgt] = (counts[tgt] || 0) + 1
    })
    connCounts.value = counts
  }

  /**
   * Unified render entry point.
   *
   * @param {Object} graphData - { nodes: [...], edges: [...] }
   * @param {Object} options
   * @param {string} options.renderMode - 'svg' | 'hybrid' | 'canvas'
   * @param {boolean} options.userSelectedRenderMode - If true, don't auto-override
   * @param {Function} options.onNodeClick - Node click handler
   * @param {Object} options.layoutParams - Per-layout parameters from composable
   */
  function render(graphData, options) {
    const container = _container.value
    if (!container || !graphData) return

    isRendering.value = true
    const { width, height } = getDimensions()

    // CRITICAL FIX: Build connCounts BEFORE any render mode
    _buildConnCounts(graphData.edges)

    // CRITICAL FIX: Only auto-select render mode if user hasn't manually chosen one.
    // options.userSelectedRenderMode is true when the user explicitly picks a mode
    // from the settings panel. When false (initial load), auto-select based on node count.
    let effectiveRenderMode = options.renderMode
    if (!options.userSelectedRenderMode) {
      const nodeCount = graphData.nodes.length
      if (nodeCount < 100) effectiveRenderMode = 'svg'
      else if (nodeCount < 300) effectiveRenderMode = 'hybrid'
      else effectiveRenderMode = 'canvas'
    }
    renderMode.value = effectiveRenderMode

    // Teardown previous render
    _simulation.value?.stop()
    _hybridRenderer.value?.destroy()

    // Delegate to render strategy
    if (effectiveRenderMode === 'hybrid') {
      _renderHybrid(container, graphData, width, height, options)
    } else {
      _renderLegacy(container, graphData, width, height, options, effectiveRenderMode)
    }

    // Wire zoom to update viewport ref
    if (_svgSelection.value && _zoomBehavior.value) {
      _zoomBehavior.value.on('zoom.viewport', (event) => {
        const t = event.transform
        viewport.value = {
          x: -t.x / t.k,
          y: -t.y / t.k,
          w: width / t.k,
          h: height / t.k,
        }
      })
    }

    // Note: isRendering is set synchronously. Since D3 rendering is synchronous,
    // Vue's reactivity batching means watchers won't see isRendering=true mid-render.
    // isLayoutLoading in GraphTab.vue (set before calling render, cleared in finally)
    // is the user-facing loading state. isRendering is a re-entrancy guard:
    // "don't call render() if already rendering."
    isRendering.value = false
  }

  /**
   * Internal: render using hybrid renderer (canvas edges + SVG nodes).
   * Direct extraction of GraphTab.vue's renderGraphHybrid() (lines 233-274).
   *
   * Contract — must set these refs:
   *   _simulation.value  = d3 force simulation instance
   *   _svgSelection.value = d3 selection of the SVG (from _hybridRenderer.nodeSvg)
   *   _zoomBehavior.value = d3 zoom behavior (from _hybridRenderer.zoom)
   *   _hybridRenderer.value = hybridRenderer instance (has .destroy())
   *
   * Dependencies received via closure/options:
   *   options.onNodeClick(d) — node click handler (passed through to renderHybrid)
   *   options.getNodeColor(type) — color function (imported from constants or passed)
   *   options.layoutParams — force layout params (linkDistance, chargeStrength, etc.)
   *
   * Color handling: D3 rendering calls getNodeColor() which must resolve
   * NEON_COLORS[type]. Since this is JS (not CSS), import NEON_COLORS directly
   * into useGraphRenderer. For D3-set attributes like stroke colors that should
   * respect the theme, use getComputedStyle(_container.value).getPropertyValue('--border')
   * at render time.
   */
  function _renderHybrid(container, graphData, width, height, options) {
    // Move code from GraphTab.vue renderGraphHybrid() here.
    // Key change: use options.layoutParams instead of hardcoded values.
    // Key change: call options.onNodeClick for click handling.
  }

  /**
   * Internal: render using legacy SVG or Canvas approach.
   * Direct extraction of GraphTab.vue's renderGraphLegacy() (lines 280-417).
   *
   * Contract — must set these refs:
   *   _simulation.value  = d3 force simulation instance
   *   _svgSelection.value = d3 selection of the root SVG
   *   _zoomBehavior.value = d3 zoom behavior
   *   _hybridRenderer.value = null (not used in legacy mode)
   *
   * Same dependency pattern as _renderHybrid.
   *
   * The renderMode param ('svg' vs 'canvas') controls whether to use
   * continuous simulation (SVG, <150 nodes) or fixed iterations (canvas, 150+).
   * This replaces the inline `nodes.length > 150` check.
   */
  function _renderLegacy(container, graphData, width, height, options, renderMode) {
    // Move code from GraphTab.vue renderGraphLegacy() here.
    // Key change: use options.layoutParams instead of hardcoded values.
    // Key change: use renderMode param instead of inline node count check.
  }

  /**
   * Apply a layout algorithm and re-render.
   * Single function replacing the 4 copy-pasted layout appliers.
   *
   * @param {string} type - Layout type from LAYOUT_TYPES
   * @param {Object} graphData - { nodes, edges }
   * @param {Object} params - Layout parameters (from useGraphState.layoutParams)
   */
  function applyLayout(type, graphData, params = {}) {
    const { width, height } = getDimensions()
    const layoutFns = {
      force: null, // Force layout is handled by re-render (simulation-based)
      hierarchical: runHierarchicalLayout,
      circular: runCircularLayout,
      clustered: runClusteredLayout,
    }

    if (type === 'force') {
      // Force layout is simulation-driven — just re-render
      return
    }

    const layoutFn = layoutFns[type]
    if (!layoutFn) return

    const result = layoutFn(graphData.nodes, graphData.edges, { width, height, ...params })

    // Update node positions from layout result
    graphData.nodes.forEach(node => {
      const positioned = result.nodes.find(n => n.id === node.id)
      if (positioned) {
        node.x = positioned.x
        node.y = positioned.y
      }
    })

    return result
  }

  function applySearchFilters(graphData, query, filters) {
    const container = _container.value
    if (!container || !graphData) return
    // Moved from GraphTab.vue
    // Uses connCounts.value (now always populated)
  }

  // Zoom + pan controls — all update viewport ref reactively
  function zoomIn() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.scaleBy, 1.4)
  }
  function zoomOut() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.scaleBy, 0.7)
  }
  function zoomReset() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.transform, d3.zoomIdentity)
  }
  // fitToScreen() omitted from v1 — it would just alias zoomReset().
  // Add later when proper fit-to-bounds (bounding box calculation) is needed.

  /**
   * Pan to a specific position (used by mini-map navigation).
   * @param {{ x: number, y: number }} position
   */
  function panTo({ x, y }) {
    if (_svgSelection.value && _zoomBehavior.value) {
      _svgSelection.value.transition().duration(300).call(
        _zoomBehavior.value.transform,
        d3.zoomIdentity.translate(-x, -y)
      )
    }
  }

  // Highlight helpers (container is internal — no need to pass it)
  function highlightNode(nodeId, className) { ... }
  function highlightPath(path) { ... }
  function highlightNeighbors(centerId, neighbors) { ... }
  function clearHighlights() { ... }

  // Lasso
  function setupLasso(onComplete) { ... }
  function teardownLasso() { ... }

  /**
   * Stop current simulation (e.g., before switching layouts).
   */
  function stopSimulation() {
    _simulation.value?.stop()
  }

  function destroy() {
    _simulation.value?.stop()
    _hybridRenderer.value?.destroy()
    _resizeObserver?.disconnect()
    _resizeObserver = null
    _svgSelection.value = null
    _zoomBehavior.value = null
    _container.value = null
  }

  // Auto-cleanup when the composable's scope is disposed (component unmount)
  onScopeDispose(destroy)

  return {
    // Reactive reads
    viewport: readonly(viewport),
    connCounts: readonly(connCounts),
    isRendering: readonly(isRendering),
    renderMode: readonly(renderMode),

    // Lifecycle
    bind,
    destroy,

    // Actions
    render,
    applyLayout,
    applySearchFilters,
    stopSimulation,
    zoomIn, zoomOut, zoomReset, panTo,
    highlightNode, highlightPath, highlightNeighbors, clearHighlights,
    setupLasso, teardownLasso,
  }
}
```

**Key decisions:**
- `shallowRef` for D3 objects — we don't want Vue deeply observing D3 internals, just tracking when the reference changes
- `_buildConnCounts()` is called BEFORE render delegation — fixes hybrid mode search highlighting. It runs on every render regardless of mode.
- `viewport` updated on every zoom event via `zoom.viewport` handler — fixes mini-map tracking
- `bind(container, onResize)` sets up ResizeObserver. The `onResize` callback is owned by GraphTab.vue so it can debounce and re-render. `destroy()` disconnects the observer. `onScopeDispose` auto-cleans if the component unmounts.
- `options.userSelectedRenderMode` flag solves the auto-override bug: initial load auto-selects, manual selection persists
- `panTo({ x, y })` is exposed for mini-map navigation
- `stopSimulation()` is exposed for layout transitions that need to stop the current simulation before starting a new one
- Layout application is a single function with a type parameter (eliminates 3x copy-paste). It returns the layout result (including clustering info) for the caller to use.
- Container is bound once via `bind()` — all subsequent calls use the internal `_container` ref, so individual functions don't need container parameters
- **Auto-select lives only in useGraphRenderer.** Remove `autoSelectRenderMode()` from `useGraphState.js` to avoid dual logic with drifting thresholds. The renderer owns the auto-select decision using `PERFORMANCE_THRESHOLDS` from constants. `useGraphState` only tracks the user's *preference* and the `_userSelectedRenderMode` flag.
- **D3-in-JS colors:** D3 rendering code that sets colors via `.attr('fill', ...)` should import `NEON_COLORS` directly. For theme-aware attributes (borders, backgrounds), read CSS variables at render time: `getComputedStyle(_container.value).getPropertyValue('--border')`. This applies to both the renderer and `GraphMiniMap.vue` (which has hardcoded cyan in its D3 code for viewport indicator).

### 2. useGraphState Fixes

```javascript
// Changes to existing composable:

import { reactive, readonly, computed } from 'vue'

// BEFORE: computed wrapping reactive (doesn't prevent mutation)
const graphState = computed(() => state)

// AFTER: readonly wrapper (actually prevents mutation)
const graphState = readonly(state)

// ADD: Missing state fields for path/neighbor results
// These were previously set via direct mutation (graphState.value.selection.pathResult = ...)
// which will break with readonly(). Add them as proper state + mutators.
//
// In createInitialState(), add to selection:
//   pathResult: [],      // Array of node IDs in shortest path
//   neighborResult: [],  // Array of node IDs in neighbor set

// ADD: Mutators for path/neighbor results
function updatePathResult(path) {
  state.selection.pathResult = Array.isArray(path) ? [...path] : []
}

function updateNeighborResult(neighbors) {
  state.selection.neighborResult = Array.isArray(neighbors) ? [...neighbors] : []
}

// ADD: Interaction mode metadata
const INTERACTION_META = {
  select: { cursor: 'pointer', instruction: null },
  path: { cursor: 'crosshair', instruction: 'Click two nodes to find shortest path' },
  neighbor: { cursor: 'cell', instruction: 'Click a node to highlight its neighbors' },
  lasso: { cursor: 'crosshair', instruction: 'Click and drag to select multiple nodes' },
}

// ADD: Computed for current mode metadata
const interactionMeta = computed(() =>
  INTERACTION_META[state.selection.mode] || INTERACTION_META.select
)

// ADD: Track whether user has manually selected a render mode
// Used by useGraphRenderer to decide whether to auto-select
function updateRenderMode(renderMode, isUserSelection = false) {
  if (Object.values(RENDER_MODES).includes(renderMode)) {
    state.renderMode = renderMode
    state._userSelectedRenderMode = isUserSelection
  }
}
// In createInitialState(), add: _userSelectedRenderMode: false

// KEEP: Layout params (Option A — wire to useGraphRenderer)
// The existing layoutParams state and localStorage persistence remain.
// useGraphRenderer.applyLayout() accepts params from this state.
// GraphSettingsPanel's new Layout Parameters accordion section
// calls updateLayoutParam() to modify these values.
```

**Note on `readonly()` migration:** After this change, any code that directly mutates `graphState.value.*` will produce a Vue warning in development and silently fail in production. All 3 known direct mutations in GraphTab.vue must be replaced:
- `graphState.value.selection.pathResult = path` → `updatePathResult(path)`
- `graphState.value.selection.neighborResult = [...]` → `updateNeighborResult(neighbors)`
- Remove `await` from `updateLayout(newLayout)` call (it's synchronous)

**Returned API additions:**
```javascript
return {
  // ... existing returns ...
  updatePathResult,
  updateNeighborResult,
  interactionMeta,  // Computed: { cursor, instruction }
}
```

### 3. GraphTopBar Changes

**Add layout quick-switch:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 [Search...]  [●Person] [●Org] [●Concept]  [Layout▾] [⚙]│
└─────────────────────────────────────────────────────────────┘
```

- Layout dropdown replaces having to open settings panel for the most common action
- Filter buttons get colored dots matching entity type neon colors
- Settings gear button stays for advanced options

**New props:**
```javascript
defineProps({
  // ... existing props ...
  currentLayout: { type: String, default: 'force' },
  interactionInstruction: { type: String, default: null },
})
```

**New emits:**
```javascript
defineEmits([
  // ... existing emits ...
  'select-layout',
])
```

**Filter button color dots (absorbs GraphLegend functionality):**
```html
<!-- Filter buttons now include a colored dot matching the entity type -->
<button
  v-for="(type, index) in entityTypes"
  :key="type"
  :class="{ active: activeFilters.includes(type) }"
  :style="{ animationDelay: `${index * 25}ms` }"
  @click="$emit('toggle-filter', type)"
>
  <span
    class="filter-dot"
    :style="{ backgroundColor: NEON_COLORS[type] || 'var(--text-tertiary)' }"
  />
  {{ type }}
</button>
```
```css
.filter-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 4px currentColor;
}
```

This means `GraphTopBar` needs to import `NEON_COLORS` from `@/constants/graph.js`. The separate `GraphLegend.vue` file is deleted since its functionality is now embedded here.

**Interaction mode indicator:**
When `interactionInstruction` is non-null, show a subtle instruction bar below the top bar:
```html
<div v-if="interactionInstruction" class="interaction-hint">
  {{ interactionInstruction }}
</div>
```

### 4. GraphSettingsPanel Changes

**Keep layout section** — layout radios remain in settings panel AND a quick-switch dropdown is added to the top bar. Both control the same state (`graphState.layout`). This is intentional: the top bar provides quick access, the settings panel provides the full layout experience alongside layout parameters.

**Restructure sections:**
```
LAYOUT
  ◉ Force  ○ Hierarchy  ○ Circular  ○ Clustered
  (unchanged from current design)

VISUAL OPTIONS
  ☑ 2.5D holographic effect
  ☐ Performance mode (no animations)

ADVANCED ▸
  Show stats panel          [toggle]
  Show mini-map             [toggle]
  Render mode               [SVG | Hybrid | Canvas]
  Interaction mode          [Select | Path | Neighbor | Lasso]
  Auto-clustering           [toggle]

LAYOUT PARAMETERS ▸ (NEW — collapsed by default)
  Link distance             [slider: 40-200]
  Charge strength           [slider: -500 to -50]
  Collision radius          [slider: 2-20]
  [Reset to Defaults]
```

**Fix emit signatures AND handler alignment** — all toggle emits pass the new boolean value explicitly, and GraphTab.vue handlers must USE the passed value instead of reading/toggling composable state independently:
```javascript
// Emits (GraphSettingsPanel)
'toggle-visual-mode': [enabled: boolean]
'toggle-performance-mode': [enabled: boolean]
'toggle-stats': [show: boolean]
'toggle-mini-map': [show: boolean]
'toggle-clustering': [enabled: boolean]

// Handlers (GraphTab.vue) — must use the emitted value
function handleVisualModeToggle(enabled) {
  updateVisualMode(enabled ? VISUAL_MODES.TWO_POINT_FIVE_D : VISUAL_MODES.TWO_D)
}
function handlePerformanceModeToggle(enabled) {
  updatePerformanceMode(enabled)
  if (graphData.value) renderer.render(graphData.value, renderOptions())
}
function handleStatsToggle(show) { showStats.value = show }
function handleMiniMapToggle(show) { showMiniMap.value = show }
function handleClusteringToggle(enabled) { updateClustering({ enabled }) }
```

**Fix positioning** — change from `position: fixed` to `position: absolute` within the graph container, so it respects the layout boundaries:
```css
.settings-panel {
  position: absolute;  /* was: fixed */
  right: 0;
  top: 0;             /* was: var(--top-bar-height) — now relative to container */
  bottom: 0;
  width: 300px;
  z-index: 50;
}
```

The backdrop similarly becomes `position: absolute` within the graph container.

**Transition handling:** The `<Transition name="slide-in-right">` currently lives inside `GraphSettingsPanel.vue`, wrapping the root `.settings-panel` div. With `position: absolute`, this stays correct — Vue's `<Transition>` is a virtual component that doesn't create a DOM node. The transition CSS classes apply directly to `.settings-panel`, which is the absolutely-positioned element. The existing CSS selectors (`.slide-in-right-enter-from`, etc.) target `.settings-panel` and will continue to work. No changes needed to the transition setup.

**Template restructuring required:** For `position: absolute` to work, both the settings panel and backdrop must be inside a `position: relative` container. The GraphTab.vue template must be restructured so that GraphSettingsPanel and the settings backdrop are children of the graph area's relative container, not siblings of the main container div:

```html
<!-- BEFORE: panel is sibling to main container -->
<GraphErrorBoundary>
  <div class="settings-backdrop" ... />
  <GraphSettingsPanel ... />
  <div class="h-full flex flex-col"> <!-- main container -->

<!-- AFTER: panel is inside the relative graph area -->
<GraphErrorBoundary>
  <div class="h-full flex flex-col">
    <GraphTopBar ... />
    <div class="flex-1 flex overflow-hidden relative"> <!-- ADD: relative -->
      <div class="settings-backdrop" ... />         <!-- MOVED inside -->
      <GraphSettingsPanel ... />                     <!-- MOVED inside -->
      <div class="flex-1 relative"> <!-- graph area -->
```

### 5. GraphStatsPanel Rewrite

**Replace emoji icons with lucide:**
```
📊 → <BarChart3 :size="14" />
🔗 → <Link :size="14" />
📦 → <Package :size="14" />
✓  → <Check :size="14" />
⚙  → <Settings :size="14" />
📈 → <TrendingUp :size="14" />
```

**Replace hardcoded colors with CSS variables:**
```css
/* BEFORE */
background: rgba(15, 23, 42, 0.8);
color: rgba(255, 255, 255, 0.95);

/* AFTER */
background: var(--surface-raised);
border: 1px solid var(--border);
color: var(--text-primary);
backdrop-filter: blur(10px);
```

**Remove scanline `::after` effect.**

**Remove connection density stat** — replace with avg connections per node (more meaningful):
```javascript
const avgConnections = computed(() => {
  if (props.nodeCount === 0) return 0
  return (props.edgeCount * 2 / props.nodeCount).toFixed(1)
})
```

### 6. GraphMiniMap Fixes

**Wire to reactive viewport** from `useGraphRenderer`:
```html
<!-- GraphTab.vue passes renderer's reactive viewport -->
<GraphMiniMap
  v-if="graphData"
  :nodes="graphData.nodes"
  :viewport="renderer.viewport.value"  <!-- Now reactive — updates on zoom/pan -->
  :mainViewBounds="mainViewBounds"
  @navigate-to="renderer.panTo"        <!-- panTo({ x, y }) exposed by renderer -->
/>
```

**Replace hardcoded dark colors with CSS variables** (same pattern as StatsPanel).

**Remove scanline effect.**

### 7. Node Detail Sidebar Animation Fix

```css
/* BEFORE: slides from left (wrong) */
.slide-in-left-enter-from { transform: translateX(-100%); }

/* AFTER: slides from right (correct — sidebar is on the right) */
.slide-in-right-sidebar-enter-from { transform: translateX(100%); }
.slide-in-right-sidebar-leave-to { transform: translateX(100%); }
```

Use a distinct transition name (`slide-in-right-sidebar`) to avoid collision with the settings panel's `slide-in-right` transition.

### 8. GraphSelectionActions Integration

Show floating toolbar when `graphState.selection.nodes.length > 1`:

```html
<!-- In GraphTab.vue, within the graph area -->
<Transition name="fade-in">
  <div v-if="graphState.selection.nodes.length > 1"
       class="absolute bottom-14 left-1/2 -translate-x-1/2 z-10">
    <GraphSelectionActions
      :selectedNodes="graphState.selection.nodes"
      :totalNodes="graphData?.nodes.length || 0"
      @action="handleSelectionAction"
    />
  </div>
</Transition>
```

**Fix GraphSelectionActions styling** — replace hardcoded dark colors with CSS variables.

### 9. Rebuild Button Fix

Move rebuild button to a position that doesn't conflict with mini-map:

```
Zoom controls: bottom-left (unchanged)
Rebuild button: bottom-right, ABOVE the mini-map when mini-map is shown
Mini-map: bottom-right corner (unchanged)
```

```html
<!-- Rebuild always visible, adjusts position when mini-map shown -->
<div :class="['absolute right-3 z-10', showMiniMap ? 'bottom-[170px]' : 'bottom-3']">
  <button @click="showRebuildModal = true">Rebuild Graph</button>
</div>
```

### 10. Dead Code Cleanup

**Delete:**
- `GraphCanvas.vue` — replaced by `useGraphRenderer`
- `GraphLayoutControls.vue` — replaced by layout params in settings panel
- `GraphLegend.vue` — functionality absorbed into GraphTopBar filter buttons with color dots
- `handleLayoutChange()` in GraphTab.vue — replaced by unified handler
- `autoSelectRenderMode()` in useGraphState.js — auto-selection now lives in `useGraphRenderer.render()` only
- `console.log` debug statements in GraphTab.vue (lines 169-177, 235, 834, 843)
- `graphState.value.selection.pathResult` / `neighborResult` direct mutations — use composable mutators

## State Management Summary

```
useGraphState (UI preferences)          useGraphRenderer (D3 rendering)
├── layout: string                      ├── viewport: ref (reactive!)
├── visualMode: string                  ├── connCounts: ref (reactive!)
├── renderMode: string                  ├── isRendering: ref
├── layoutParams: per-layout configs    ├── render()
├── clustering: { enabled, ... }        ├── applyLayout()
├── selection: { nodes, mode, ... }     ├── applySearchFilters()
├── view: { zoom, pan }                 ├── zoom controls
├── performance: { mode, fps }          ├── highlight helpers
└── interactionMeta: computed           └── destroy()
```

GraphTab.vue coordinates between them — complete layout change handler:
```javascript
// Single handler used by BOTH top bar dropdown and settings panel radios
async function handleLayoutChange(layoutType) {
  graphState.updateLayout(layoutType)
  if (!graphData.value) return

  renderer.stopSimulation()
  isLayoutLoading.value = true

  try {
    if (layoutType === LAYOUT_TYPES.FORCE) {
      // Force layout is simulation-driven — re-render fully
      renderer.render(graphData.value, renderOptions())
    } else {
      // Static layouts: compute positions, then re-render
      const result = renderer.applyLayout(layoutType, graphData.value, graphState.layoutParams[layoutType])

      // Consume clustering info if layout provides it
      if (result?.clustering) {
        updateClustering({ clusterCount: result.clustering.clusterCount })
      }

      // Re-render with updated node positions
      renderer.render(graphData.value, renderOptions())
    }
  } finally {
    isLayoutLoading.value = false
  }
}

// Helper to build render options from current state
function renderOptions() {
  return {
    renderMode: graphState.renderMode,
    userSelectedRenderMode: graphState._userSelectedRenderMode,
    onNodeClick: selectNode,
    getNodeColor,
    layoutParams: graphState.layoutParams[graphState.layout],
  }
}
```

Other coordination flows:
- User zooms → renderer updates `viewport` ref → mini-map reactively updates
- User searches → GraphTab calls `renderer.applySearchFilters()`
- User changes render mode in settings → calls `graphState.updateRenderMode(mode, true)` then `renderer.render(graphData, renderOptions())`

## Edge Cases

1. **Settings panel + node selection:** Panel is now `position: absolute` within graph container, so it doesn't overlap the navigation rail. Node sidebar and settings panel can coexist (graph area shrinks for sidebar, panel overlays on top).

2. **Layout quick-switch during rendering:** Disable the dropdown while `renderer.isRendering` is true. Show a subtle loading indicator on the dropdown.

3. **Window resize:** `useGraphRenderer` should attach a ResizeObserver to the container and re-render on size change. This replaces the `height || 500` fallback hack.

4. **Hybrid → SVG mode switch mid-session:** `renderer.render()` fully tears down and recreates. No incremental patching between modes.

5. **Many entity types (>6):** Filter buttons in top bar overflow horizontally with `overflow-x: auto` (existing behavior). Layout dropdown stays visible due to `flex-shrink: 0`.

## Lasso Selection Limit

The current code has two inconsistent limits: `addNodeToSelection` limits to 10 nodes, but lasso completion limits to 50. Standardize on **50** for lasso (bulk selection tool) and **10** for manual multi-select (click-based). Document in useGraphState that the 10-node limit applies to `addNodeToSelection` only; lasso bypasses it by calling `updateSelection({ nodes: [...] })` directly.

## Sidebar Animation Note

Commit `e464386` ("fix: correct sidebar animation direction") was attempted but did not fix the issue — the transition name remains `slide-in-left` with `translateX(-100%)`. This redesign replaces it with `slide-in-right-sidebar` using `translateX(100%)`.

## Success Criteria

1. Layout switching works from both top bar dropdown and settings panel (both control `graphState.layout`)
2. Render mode selection persists across re-renders (auto-select only on initial load, not after manual selection)
3. Mini-map viewport updates reactively on zoom/pan (via `useGraphRenderer.viewport` ref)
4. All graph components render correctly in both light and dark mode (no hardcoded `rgba(15, 23, 42, ...)` colors)
5. Search highlighting works in hybrid render mode (`connCounts` populated for all modes)
6. GraphTab.vue is under 500 lines (rendering extracted to `useGraphRenderer`)
7. No `console.log` debug statements in production code
8. No hardcoded color values in graph components — all use CSS custom properties
9. Interaction modes show cursor change and instruction text via `interactionMeta` computed
10. `--surface-elevated` and `--color-primary` CSS variables defined in `main.css` for both light and dark themes
11. `readonly()` on graphState — no direct mutations; `pathResult` and `neighborResult` use dedicated mutators
12. Build succeeds, no regressions in existing functionality
