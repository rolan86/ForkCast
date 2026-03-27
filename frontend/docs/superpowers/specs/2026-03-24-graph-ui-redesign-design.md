# Graph UI Redesign Design

**Date:** 2026-03-24
**Author:** Claude
**Status:** Approved (v3 - Enhanced Visual Design)

## Problem Statement

The current graph UI has become cluttered with scattered controls:
- Multiple floating panels (toolbar, stats, mini-map) create visual noise
- Selection controls are disconnected from the graph
- Resizing behavior is broken
- Original simple, clean UI was better organized

## Goals

1. **Clean primary interface**: Search and filters always visible, minimal chrome
2. **Advanced features accessible but hidden**: Layout controls, visual options behind settings panel
3. **Maximize graph space**: Graph should be the main focus
4. **Preserve useful features**: Keep what users actually use (search, filters, layouts)

## User Research Findings

**Primary workflow:** Both exploration and analysis equally
**Regularly used features:** Search & filters, Layout controls
**Preferred layout:** Minimal top bar + collapsible settings panel

## Design: Approach A - Clean Top Bar + Collapsible Panel

### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 [Search...]    [Person] [Org] [Concept]    [⚙️ Settings] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                       GRAPH AREA                            │
│                  (takes full remaining space)                │
│                                                             │
│ [+][-][⟲]                                          [Rebuild]│
│ bottom-left                                         bottom-right│
└─────────────────────────────────────────────────────────────┘

Settings panel (slides in from right when ⚙️ clicked):
┌─────────────────────────────────┐
│ LAYOUT                          │
│ ◉ Force  ○ Hierarchy           │
│ ○ Circular  ○ Clustered        │
│                                 │
│ VISUAL OPTIONS                  │
│ ☑ 2.5D holographic effect      │
│ ☐ Performance mode             │
│                                 │
│ Advanced ▸ (click to expand)    │
│   ┌─────────────────────────┐  │
│   │ ☑ Show stats panel      │  │
│   │ ☐ Show mini-map         │  │
│   │ Render: [SVG ▾]         │  │
│   │ Mode: [Select ▾]        │  │
│   │ ☐ Auto-clustering       │  │
│   └─────────────────────────┘  │
│                                 │
│                [× Close]       │
└─────────────────────────────────┘
```

## Component Changes

### Remove
- `GraphToolbar.vue` - Replaced by settings panel
- `GraphStatsPanel.vue` - Moved into Advanced section (as optional checkbox)
- `GraphMiniMap.vue` - Moved into Advanced section (as optional checkbox)

### Leave Unchanged
- `GraphCanvas.vue` - Not currently used, created but never integrated; leave as-is for future consideration
- `GraphLayoutControls.vue` - Keep for potential future use, but NOT included in settings panel for v1

### Create New

#### 1. GraphTopBar.vue

**Props:**
```typescript
interface Props {
  searchQuery: string
  entityTypes: string[]
  activeFilters: string[]
  settingsPanelOpen: boolean
}
```

**Emits:**
```typescript
const emit = defineEmits<{
  'update:searchQuery': [value: string]
  'toggle-filter': [type: string]
  'toggle-settings': []
}>()
```

**Template structure:**
```vue
<div class="graph-top-bar">
  <div class="search-section">
    <Search :size="14" />
    <input
      :value="searchQuery"
      @input="$emit('update:searchQuery', $event.target.value)"
      placeholder="Search entities..."
    />
  </div>
  <div v-if="entityTypes.length > 0" class="filter-section">
    <button
      v-for="(type, index) in entityTypes"
      :key="type"
      :class="{ active: activeFilters.includes(type) }"
      :style="{ animationDelay: `${index * 25}ms` }"
      @click="$emit('toggle-filter', type)"
    >
      {{ type }}
    </button>
  </div>
  <button
    class="settings-toggle"
    :class="{ active: settingsPanelOpen }"
    @click="$emit('toggle-settings')"
  >
    <Settings :size="16" />
  </button>
</div>
```

**Filter behavior:**
- Toggle buttons: click to activate, click again to deactivate
- Visual feedback: active button shows full color with glow, inactive shows dimmed
- Staggered entrance animation on mount
- "All off" state = show all entities (no filtering)
- Filter state persists in `activeFilters` ref

#### 2. GraphSettingsPanel.vue

**Props:**
```typescript
interface Props {
  isOpen: boolean
  currentLayout: string
  visualMode: string
  performanceMode: boolean
  renderMode: string
  interactionMode: string
  showStats: boolean
  showMiniMap: boolean
  clusteringEnabled: boolean
  isLoading?: boolean
}
```

**Emits:**
```typescript
const emit = defineEmits<{
  'close': []
  'select-layout': [layout: string]
  'toggle-visual-mode': []
  'toggle-performance-mode': []
  'select-render-mode': [mode: string]
  'select-interaction-mode': [mode: string]
  'toggle-stats': []
  'toggle-mini-map': []
  'toggle-clustering': []
}>()
```

**Internal state:**
```typescript
const advancedExpanded = ref(false)

function toggleAdvanced() {
  advancedExpanded.value = !advancedExpanded.value
}
```

**Accordion behavior:**
- Click "Advanced ▸" to expand, "Advanced ▾" to collapse
- Uses grid-template-rows for smooth height animation (better than max-height)
- Chevicon rotates 90deg during transition
- Advanced state NOT persisted (resets to collapsed on panel close)

**Loading state:**
- When `isLoading` prop is true, show loading indicator in panel
- Applies to layout switches which may take time

### Keep Unchanged
- `GraphErrorBoundary.vue`
- `NodeDetailSidebar.vue` (right panel for selected node)
- `ConfirmModal.vue` (rebuild confirmation)

### GraphTab.vue Changes

**Remove:**
- GraphToolbar import and usage
- GraphStatsPanel from template (moved to settings panel)
- GraphMiniMap from template (moved to settings panel)

**Add:**
- GraphTopBar import and usage
- GraphSettingsPanel import and usage
- Local state: `settingsPanelOpen`, `showStats`, `showMiniMap`, `isLayoutLoading`

**Move code:**
- Search/filter HTML moves from GraphTab.vue to GraphTopBar.vue
- Search/filter logic stays in GraphTab.vue (searchQuery, activeFilters refs)

## State Management

```javascript
// Local state in GraphTab.vue
const settingsPanelOpen = ref(false)
const showStats = ref(false)
const showMiniMap = ref(false)
const isLayoutLoading = ref(false)

function toggleSettings() {
  settingsPanelOpen.value = !settingsPanelOpen.value
}

function closeSettings() {
  settingsPanelOpen.value = false
  // Reset advanced section state when panel closes
  // (handled internally by GraphSettingsPanel)
}

async function handleLayoutChange(newLayout) {
  isLayoutLoading.value = true
  try {
    // Apply layout change
    await updateLayout(newLayout)
    if (graphData.value) {
      renderGraph()
    }
  } finally {
    isLayoutLoading.value = false
  }
}
```

**Panel closes when:**
- User clicks the X button
- User clicks outside the panel (backdrop)
- User clicks Rebuild (auto-close before modal appears)

**Panel stays open when:**
- User selects a layout (for rapid comparison)
- User toggles any option

**Settings panel state:**
- Does NOT persist across navigation (always closed on fresh load)
- Advanced section state does NOT persist (always collapsed on open)

**Graph state persistence:**
- Layout selection persists via useGraphState
- Visual mode persists via useGraphState
- Performance mode persists via useGraphState
- Show stats/mini-map toggles DO NOT persist (always default to false)

## Z-Index Layering

```
z-50  Settings panel
z-40  Settings backdrop
z-30  (reserved for future overlays)
z-20  Top bar
z-10  (base level for graph container)
```

**Note:** Node detail sidebar is NOT z-indexed - it's a normal flex item in the container, which is correct behavior.

## Edge Cases

1. **Settings panel open + user selects a node:**
   - Settings panel stays open
   - Node detail sidebar appears on the right
   - Graph area shrinks to accommodate sidebar

2. **Settings panel open + user clicks Rebuild:**
   - Settings panel closes automatically
   - Rebuild modal appears

3. **Window resize while panel is open:**
   - Panel remains open
   - On < 768px viewport: panel width becomes 80% of screen

4. **Search query is very long:**
   - Input has `flex: 1` so it takes available space
   - Filter buttons have fixed width, won't overflow
   - Settings button fixed width

5. **No entity types available (empty graph):**
   - Filter section is hidden when `entityTypes.length === 0`
   - Search still functional

6. **Layout change in progress:**
   - Loading indicator shows in settings panel
   - Layout radio buttons disabled during load
   - Other options remain interactive

## Responsive Design

```css
/* Desktop (default) */
.graph-top-bar {
  flex-direction: row;
}

.settings-panel {
  width: 300px;
}

/* Mobile (< 768px) */
@media (max-width: 767px) {
  .graph-top-bar {
    flex-wrap: wrap;
    padding: 8px;
  }

  .search-section {
    width: 100%;
    order: 1;
  }

  .filter-section {
    width: 100%;
    order: 2;
    overflow-x: auto;
  }

  .settings-toggle {
    position: absolute;
    top: 8px;
    right: 8px;
    order: 3;
  }

  .settings-panel {
    width: 85%;
  }
}
```

## Visual Design & Polish

### Typography

```css
/* Top bar - system fonts with tight spacing */
.graph-top-bar {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: -0.01em;
}

/* Settings panel headers */
.settings-header {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

/* Filter buttons - uppercase for consistency */
.filter-section button {
  text-transform: uppercase;
  letter-spacing: 0.02em;
  font-weight: 600;
}
```

### Top Bar - Enhanced Styling

```css
.graph-top-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  height: 53px;
}

/* Search section with focus ring */
.search-section {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-sunken);
  border-radius: 8px;
  padding: 6px 12px;
  border: 1px solid transparent;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 0;
}

.search-section:focus-within {
  border-color: var(--color-primary, rgba(0, 212, 255, 0.3));
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

.search-section input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
}

.search-section input::placeholder {
  color: var(--text-tertiary);
}

/* Enhanced filter buttons */
.filter-section {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.filter-section button {
  padding: 6px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  border: 1px solid transparent;
  white-space: nowrap;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  animation: filter-enter 300ms ease-out forwards;
  opacity: 0;
}

@keyframes filter-enter {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.filter-section button:hover {
  background: var(--surface-elevated);
  transform: translateY(-1px);
  border-color: var(--border);
}

.filter-section button.active {
  background: var(--color-primary, #00d4ff);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 212, 255, 0.3);
  border-color: var(--color-primary);
  opacity: 1;
}

/* Settings toggle with presence */
.settings-toggle {
  padding: 8px;
  border-radius: 8px;
  background: var(--surface-sunken);
  border: none;
  cursor: pointer;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-toggle:hover {
  background: var(--surface-elevated);
  transform: scale(1.05);
}

.settings-toggle.active {
  background: var(--color-primary, #00d4ff);
  color: white;
  box-shadow: 0 2px 12px rgba(0, 212, 255, 0.4);
}

.settings-toggle.active svg {
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}
```

### Settings Panel - Enhanced Styling

```css
.settings-panel {
  position: fixed;
  right: 0;
  top: 53px;
  bottom: 0;
  width: 300px;
  background: var(--surface-raised);
  border-left: 1px solid var(--border);
  box-shadow:
    -4px 0 24px rgba(0, 0, 0, 0.15),
    -1px 0 8px rgba(0, 0, 0, 0.1),
    inset 1px 0 0 rgba(255, 255, 255, 0.05);
  overflow-y: auto;
  z-index: 50;
}

.settings-backdrop {
  position: fixed;
  inset: 53px 0 0 0;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(2px);
  z-index: 40;
  transition: opacity 200ms;
}

/* Settings sections with visual hierarchy */
.settings-section {
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.06));
}

.settings-section:last-child {
  border-bottom: none;
}

.settings-header {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

/* Enhanced layout radio buttons */
.layout-radios {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.layout-radio {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 13px;
  font-weight: 500;
}

.layout-radio:hover {
  background: var(--surface-elevated);
  border-color: var(--border);
}

.layout-radio.selected {
  background: rgba(0, 212, 255, 0.15);
  border-color: var(--color-primary, rgba(0, 212, 255, 0.3));
  color: var(--color-primary, #00d4ff);
}

.layout-radio:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.layout-radio input[type="radio"] {
  appearance: none;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
  transition: all 150ms;
}

.layout-radio input[type="radio"]:checked {
  border-color: var(--color-primary, #00d4ff);
  background: var(--color-primary, #00d4ff);
}

.layout-radio input[type="radio"]:checked::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 6px;
  height: 6px;
  background: white;
  border-radius: 50%;
}

/* Checkbox styling for options */
.option-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: color 150ms;
}

.option-checkbox:hover {
  color: var(--text-primary);
}

.option-checkbox input[type="checkbox"] {
  appearance: none;
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-radius: 4px;
  flex-shrink: 0;
  transition: all 150ms;
  position: relative;
}

.option-checkbox input[type="checkbox"]:checked {
  background: var(--color-primary, #00d4ff);
  border-color: var(--color-primary, #00d4ff);
}

.option-checkbox input[type="checkbox"]:checked::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-size: 12px;
  font-weight: bold;
}

/* Loading indicator */
.settings-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(0, 212, 255, 0.1);
  border-radius: 6px;
  margin: 12px 20px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-primary, #00d4ff);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 600ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 12px;
  color: var(--color-primary, #00d4ff);
  font-weight: 500;
}

/* Enhanced accordion */
.accordion-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 0;
  cursor: pointer;
  user-select: none;
}

.accordion-content {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.accordion-content.expanded {
  grid-template-rows: 1fr;
}

.accordion-inner {
  overflow: hidden;
}

.accordion-chevron {
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.accordion-chevron.open {
  transform: rotate(90deg);
}

/* Close button */
.settings-close {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 8px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all 150ms;
}

.settings-close:hover {
  background: var(--surface-sunken);
  color: var(--text-secondary);
}
```

### Enhanced Animations

```css
/* Panel slide with better easing */
.slide-in-right-enter-active .settings-panel,
.slide-in-right-leave-active .settings-panel {
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-in-right-enter-active .settings-backdrop,
.slide-in-right-leave-active .settings-backdrop {
  transition: opacity 200ms;
}

.slide-in-right-enter-from .settings-panel {
  transform: translateX(100%);
}

.slide-in-right-leave-to .settings-panel {
  transform: translateX(100%);
}

.slide-in-right-enter-from .settings-backdrop,
.slide-in-right-leave-to .settings-backdrop {
  opacity: 0;
}

/* Staggered filter button delays */
.filter-section button:nth-child(1) { animation-delay: 50ms; }
.filter-section button:nth-child(2) { animation-delay: 75ms; }
.filter-section button:nth-child(3) { animation-delay: 100ms; }
.filter-section button:nth-child(4) { animation-delay: 125ms; }
.filter-section button:nth-child(5) { animation-delay: 150ms; }
```

## Template Structure

```vue
<template>
  <!-- Empty state -->
  <div v-if="viewState === 'empty'" class="p-6">
    <EmptyState ... />
  </div>

  <!-- Building state -->
  <div v-else-if="viewState === 'building'" class="p-6">
    <ProgressPanel ... />
  </div>

  <!-- Ready state -->
  <GraphErrorBoundary v-else @reset="handleGraphReset">
    <!-- Settings backdrop -->
    <Transition name="slide-in-right">
      <div
        v-if="settingsPanelOpen"
        class="settings-backdrop"
        @click="closeSettings"
      />
    </Transition>

    <!-- Settings panel -->
    <GraphSettingsPanel
      :isOpen="settingsPanelOpen"
      :currentLayout="graphState.layout"
      :visualMode="graphState.visualMode"
      :performanceMode="graphState.performance.performanceMode"
      :renderMode="graphState.renderMode"
      :interactionMode="graphState.selection.mode"
      :showStats="showStats"
      :showMiniMap="showMiniMap"
      :clusteringEnabled="graphState.clustering.enabled"
      :isLoading="isLayoutLoading"
      @close="closeSettings"
      @select-layout="handleLayoutChange"
      @toggle-visual-mode="handleVisualModeToggle"
      @toggle-performance-mode="handlePerformanceModeToggle"
      @select-render-mode="handleRenderModeChange"
      @select-interaction-mode="handleModeChange"
      @toggle-stats="showStats = $event"
      @toggle-mini-map="showMiniMap = $event"
      @toggle-clustering="handleClusteringToggle"
    />

    <!-- Main container -->
    <div class="h-full flex flex-col">
      <!-- Top bar -->
      <GraphTopBar
        :searchQuery="searchQuery"
        :entityTypes="entityTypes"
        :activeFilters="activeFilters"
        :settingsPanelOpen="settingsPanelOpen"
        @update:searchQuery="searchQuery = $event"
        @toggle-filter="toggleFilter"
        @toggle-settings="toggleSettings"
      />

      <!-- Graph area container -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Main graph area -->
        <div class="flex-1 relative">
          <div ref="svgContainer" class="w-full h-full" />

          <!-- Stats panel (conditionally rendered) -->
          <Transition name="fade-in">
            <div v-if="showStats" class="absolute top-3 left-3 z-10">
              <GraphStatsPanel ... />
            </div>
          </Transition>

          <!-- Mini-map (conditionally rendered) -->
          <Transition name="fade-in">
            <div v-if="showMiniMap" class="absolute bottom-3 right-3 z-10">
              <GraphMiniMap ... />
            </div>
          </Transition>

          <!-- Zoom controls (bottom-left) -->
          <div class="absolute bottom-3 left-3 flex gap-1 z-10">
            <button @click="zoomIn"><Plus :size="14" /></button>
            <button @click="zoomOut"><Minus :size="14" /></button>
            <button @click="zoomReset"><RotateCcw :size="12" /></button>
          </div>

          <!-- Rebuild button (bottom-right, unless mini-map is shown) -->
          <Transition name="fade-in">
            <div v-if="!showMiniMap" class="absolute bottom-3 right-3 z-10">
              <button @click="showRebuildModal = true">Rebuild Graph</button>
            </div>
          </Transition>
        </div>

        <!-- Node detail sidebar (appears when node selected) -->
        <Transition name="slide-in-left">
          <div
            v-if="selectedNode"
            class="w-[260px] border-l shrink-0 overflow-y-auto"
            :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)' }"
          >
            <!-- Node details content (unchanged from original) -->
          </div>
        </Transition>
      </div>
    </div>

    <!-- Rebuild confirmation modal -->
    <ConfirmModal ... />
  </GraphErrorBoundary>
</template>
```

## Implementation Notes

1. **Preserve existing functionality:**
   - All layout algorithms continue to work
   - useGraphState composable remains unchanged
   - Existing event handlers are preserved
   - Graph rendering logic stays in GraphTab.vue

2. **Search/filter code migration:**
   - HTML moves from GraphTab.vue to GraphTopBar.vue
   - Logic (refs, computed, watchers) stays in GraphTab.vue
   - Props/emits bridge between components

3. **Toast notifications:**
   - REMOVED from v1 specification
   - Layout changes are immediate and visual (no toast needed)
   - Loading indicator in panel shows layout change progress

4. **GraphCanvas.vue:**
   - Exists but not integrated in current codebase
   - Leave unchanged for future consideration
   - Not part of this redesign

5. **GraphLayoutControls.vue:**
   - Sliders for layout parameters (link distance, charge, etc.)
   - NOT included in v1 settings panel
   - Can be added to Advanced section in future if needed

6. **Visual polish priorities:**
   - Typography: Use system fonts with careful weight/letter-spacing
   - Filter buttons: Transform on hover, glow on active
   - Settings toggle: Scale on hover, glow animation when active
   - Backdrop: Blur + 0.2 opacity (more visible than original 0.05)
   - Panel shadow: Layered shadows for depth
   - Loading state: Spinner + text when changing layouts
   - Animations: Cubic-bezier easing for premium feel

## Success Criteria

1. ✅ Top bar shows only search, filters, and settings button
2. ✅ Graph area takes maximum available space
3. ✅ Settings panel opens smoothly with backdrop
4. ✅ Layout switching is 1 click away (settings → layout radio)
5. ✅ Advanced features are hidden but accessible
6. ✅ UI feels clean and uncluttered
7. ✅ Visual polish: hover states, focus rings, smooth animations
8. ✅ Build succeeds, no regressions
9. ✅ Responsive design works on mobile

## Open Questions

None - design approved by stakeholder, review feedback addressed, visual design enhanced.
