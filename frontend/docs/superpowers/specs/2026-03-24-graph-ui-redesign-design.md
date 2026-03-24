# Graph UI Redesign Design

**Date:** 2026-03-24
**Author:** Claude
**Status:** Approved

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
│ Layout        ○ Stats           │
│ ◉ Force                       │
│ ○ Hierarchy                    │
│ ○ Circular                     │
│ ○ Clustered                    │
│                                │
│ Visual Options                 │
│ ○ 2.5D holographic effect      │
│ ○ Performance mode             │
│                                │
│ Advanced ▸                     │
│   • Stats panel                │
│   • Mini-map                   │
│   • Render mode                │
│   • Interaction mode           │
│   • Auto-clustering            │
│                                │
│                [× Close]       │
└─────────────────────────────────┘
```

## Component Changes

### Remove
- `GraphToolbar.vue` - Replaced by settings panel
- `GraphStatsPanel` - Moved into Advanced section
- `GraphMiniMap` - Moved into Advanced section

### Create New
1. **GraphTopBar.vue** - Simple top bar component
   - Search input with icon
   - Entity type filter buttons
   - Settings toggle button

2. **GraphSettingsPanel.vue** - Collapsible settings panel
   - Layout radio buttons
   - Visual options checkboxes
   - Advanced accordion section
   - Slide-in animation from right
   - Click-away backdrop

### Keep Unchanged
- `GraphErrorBoundary.vue`
- `NodeDetailSidebar.vue` (right panel for selected node)
- `ConfirmModal.vue` (rebuild confirmation)

### GraphTab.vue Changes
- Remove GraphToolbar import and usage
- Add GraphTopBar and GraphSettingsPanel imports
- Simplify template structure to match original clean design

## State Management

```javascript
// Local state in GraphTab.vue
const settingsPanelOpen = ref(false)

function toggleSettings() {
  settingsPanelOpen.value = !settingsPanelOpen.value
}

function closeSettings() {
  settingsPanelOpen.value = false
}
```

**Panel closes when:**
- User clicks the X button
- User clicks outside the panel (backdrop)
- User selects a layout (auto-close for quick actions)

**Layout selection:**
- Immediately applies new layout
- Shows brief toast: "Switched to Hierarchy layout"
- Panel stays open for further adjustments

**Advanced section:**
- Collapsed by default
- Click "Advanced ▸" to expand
- Contains rarely-used features

## Styling

### Top Bar
```css
.graph-top-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
}

.search-section {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-sunken);
  border-radius: 8px;
  padding: 6px 12px;
}

.settings-toggle {
  padding: 8px;
  border-radius: 8px;
  background: var(--surface-sunken);
}

.settings-toggle:hover {
  background: var(--border);
}
```

### Settings Panel
```css
.settings-panel {
  position: fixed;
  right: 0;
  top: 53px;
  bottom: 0;
  width: 300px;
  background: var(--surface-raised);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
  overflow-y: auto;
}

.slide-in-right-enter-active,
.slide-in-right-leave-active {
  transition: transform 200ms ease-out;
}

.slide-in-right-enter-from,
.slide-in-right-leave-to {
  transform: translateX(100%);
}

.settings-backdrop {
  position: fixed;
  inset: 53px 0 0 0;
  background: rgba(0, 0, 0, 0.05);
}
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
    <div
      v-if="settingsPanelOpen"
      class="settings-backdrop"
      @click="closeSettings"
    />

    <!-- Settings panel -->
    <GraphSettingsPanel
      :isOpen="settingsPanelOpen"
      :currentLayout="graphState.layout"
      :visualMode="graphState.visualMode"
      :performanceMode="graphState.performance.performanceMode"
      :renderMode="graphState.renderMode"
      :interactionMode="graphState.selection.mode"
      :stats="graphStats"
      @close="closeSettings"
      @select-layout="handleLayoutChange"
      @toggle-visual-mode="handleVisualModeToggle"
      @toggle-performance-mode="handlePerformanceModeToggle"
      @select-render-mode="handleRenderModeChange"
      @select-interaction-mode="handleModeChange"
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

      <!-- Graph area -->
      <div class="flex-1 relative">
        <div ref="svgContainer" class="w-full h-full" />

        <!-- Zoom controls (bottom-left) -->
        <div class="absolute bottom-3 left-3 flex gap-1">
          <button @click="zoomIn"><Plus :size="14" /></button>
          <button @click="zoomOut"><Minus :size="14" /></button>
          <button @click="zoomReset"><RotateCcw :size="12" /></button>
        </div>

        <!-- Rebuild button (bottom-right) -->
        <div class="absolute bottom-3 right-3">
          <button @click="showRebuildModal = true">Rebuild Graph</button>
        </div>
      </div>

      <!-- Node detail sidebar -->
      <div
        v-if="selectedNode"
        class="w-[260px] border-l shrink-0 overflow-y-auto"
      >
        <!-- Node details content -->
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

2. **Z-index layering:**
   - Settings panel: z-50
   - Backdrop: z-40
   - Node detail sidebar: z-30
   - Top bar: z-20

3. **Animation:**
   - Panel slide: 200ms ease-out
   - Advanced accordion: 150ms ease-out
   - Settings button hover: 150ms

4. **Responsive considerations:**
   - On mobile (< 768px): Panel takes 80% width
   - Settings button remains accessible
   - Zoom controls remain accessible

## Success Criteria

1. Top bar shows only search, filters, and settings button
2. Graph area takes maximum available space
3. Settings panel opens smoothly with backdrop
4. Layout switching is 1-2 clicks away
5. Advanced features are hidden but accessible
6. UI feels clean and uncluttered
7. Build succeeds, no regressions

## Open Questions

None - design approved by stakeholder.
