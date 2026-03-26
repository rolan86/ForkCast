<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import { buildGraph, getGraphData, streamGraphBuild } from '@/api/graphs.js'
import { useGraphState } from '@/composables/useGraphState.js'
import { useGraphRenderer } from '@/composables/useGraphRenderer.js'
import { NEON_COLORS, LAYOUT_TYPES, VISUAL_MODES, INTERACTION_MODES } from '@/constants/graph.js'
import { findShortestPath, findNeighbors, findNodesInLasso } from '@/utils/graph/interactions/modes.js'
import EmptyState from '@/components/EmptyState.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import GraphErrorBoundary from '@/components/graph/GraphErrorBoundary.vue'
import GraphTopBar from '@/components/graph/GraphTopBar.vue'
import GraphSettingsPanel from '@/components/graph/GraphSettingsPanel.vue'
import GraphStatsPanel from '@/components/graph/GraphStatsPanel.vue'
import GraphMiniMap from '@/components/graph/GraphMiniMap.vue'
import GraphSelectionActions from '@/components/graph/GraphSelectionActions.vue'
import { Plus, Minus, RotateCcw } from 'lucide-vue-next'

const route = useRoute()
const store = useProjectStore()
const projectId = computed(() => route.params.id)

// Graph state composable for UI state management
const {
  graphState,
  updateLayout,
  updateSelection,
  updateView,
  updateClustering,
  updateVisualMode,
  updateRenderMode,
  updatePerformanceMode,
  updatePathResult,
  updateNeighborResult,
  interactionMeta,
} = useGraphState()

// Renderer composable — owns all D3 state
const renderer = useGraphRenderer()

// State: 'empty' | 'building' | 'ready'
const viewState = ref('empty')
const buildError = ref('')
const buildDisconnected = ref(false)
const showRebuildModal = ref(false)
const graphData = ref(null)
const selectedNode = ref(null)
const searchQuery = ref('')
const activeFilters = ref([])

// Settings panel state
const settingsPanelOpen = ref(false)
const showStats = ref(false)
const showMiniMap = ref(false)
const isLayoutLoading = ref(false)

// DOM ref
const svgContainer = ref(null)
let sseConnection = null

const GRAPH_BUILD_STEPS = [
  { label: 'Extract text', stageNames: ['extracting_text'] },
  { label: 'Chunk', stageNames: ['chunking'] },
  { label: 'Ontology', stageNames: ['generating_ontology'] },
  { label: 'Entities', stageNames: ['extracting_entities', 'deduplicating'] },
  { label: 'Build graph', stageNames: ['building_graph', 'indexing', 'registering'] },
]

// Use neon colors from constants (2.5D styling)
// Fallback to original colors for entity types not yet in NEON_COLORS
const getNodeColor = (type) => {
  return NEON_COLORS[type] || {
    Person: '#3b82f6',
    Organization: '#8b5cf6',
    Concept: '#6366f1',
    Topic: '#10b981',
    Event: '#f59e0b',
  }[type] || '#6366f1'
}

onMounted(() => {
  if (store.currentGraph && (store.currentGraph.status === 'complete' || store.currentGraph.status === 'built')) {
    loadGraphData()
  } else {
    viewState.value = 'empty'
  }
})

onUnmounted(() => {
  sseConnection?.close()
  // renderer auto-cleans via onScopeDispose
})

async function loadGraphData() {
  try {
    graphData.value = await getGraphData(projectId.value)
    viewState.value = 'ready'
    await nextTick()
    if (svgContainer.value) {
      renderer.bind(svgContainer.value, () => {
        if (graphData.value) renderGraph()
      })
    }
    renderGraph()
  } catch {
    viewState.value = 'empty'
  }
}

function startBuild() {
  viewState.value = 'building'
  buildError.value = ''
  buildDisconnected.value = false
  store.resetGraphBuildProgress()

  buildGraph(projectId.value).catch(err => {
    if (!buildError.value) buildError.value = err.message || 'Build failed'
  })

  sseConnection = streamGraphBuild(projectId.value, {
    onMessage(data) {
      buildDisconnected.value = false
      store.updateGraphBuildProgress(data)
    },
    onError(message) {
      buildError.value = message
    },
    async onComplete() {
      await store.fetchGraph(projectId.value)
      await loadGraphData()
    },
    onDisconnect() {
      buildDisconnected.value = true
    },
  })
}

function cancelBuild() {
  sseConnection?.close()
  viewState.value = 'empty'
}

function retryBuild() {
  sseConnection?.close()
  startBuild()
}

function confirmRebuild() {
  showRebuildModal.value = false
  settingsPanelOpen.value = false // Close settings panel
  startBuild()
}

// Zoom controls — delegate to renderer
function zoomIn() { renderer.zoomIn() }
function zoomOut() { renderer.zoomOut() }
function zoomReset() { renderer.zoomReset() }

function renderGraph() {
  if (!svgContainer.value || !graphData.value) return
  renderer.render(graphData.value, renderOptions())
  setupLassoEvents()
}

function renderOptions() {
  return {
    renderMode: graphState.renderMode,
    userSelectedRenderMode: graphState._userSelectedRenderMode,
    onNodeClick: selectNode,
    getNodeColor,
    layoutParams: graphState.layoutParams[graphState.layout],
  }
}

function setupLassoEvents() {
  if (!svgContainer.value || graphState.selection.mode !== INTERACTION_MODES.LASSO) return
  renderer.setupLasso((lassoPoints) => {
    const selectedIds = findNodesInLasso(graphData.value.nodes, lassoPoints)
    if (selectedIds.length > 0) {
      const limitedIds = selectedIds.slice(0, 50)
      updateSelection({ nodes: limitedIds })
    }
  })
}

function selectNode(d) {
  const currentMode = graphState.selection.mode

  switch (currentMode) {
    case INTERACTION_MODES.PATH:
      handlePathModeSelect(d)
      break
    case INTERACTION_MODES.NEIGHBOR:
      handleNeighborModeSelect(d)
      break
    case INTERACTION_MODES.SELECT:
    default:
      handleSelectMode(d)
      break
  }
}

function handleSelectMode(d) {
  selectedNode.value = {
    ...d,
    connections: graphData.value.edges
      .filter(e => (e.source.id || e.source) === d.id || (e.target.id || e.target) === d.id)
      .map(e => ({
        node: (e.source.id || e.source) === d.id ? (e.target.id || e.target) : (e.source.id || e.source),
        label: e.label,
        type: graphData.value.nodes.find(n => n.id === ((e.source.id || e.source) === d.id ? (e.target.id || e.target) : (e.source.id || e.source)))?.type,
      })),
  }
  updateSelection({ nodes: [d.id] })
}

function handlePathModeSelect(d) {
  const pathStart = graphState.selection.pathStart
  const pathEnd = graphState.selection.pathEnd

  if (!pathStart) {
    updateSelection({ pathStart: d.id })
    renderer.highlightNode(d.id, 'path-start')
  } else if (!pathEnd && d.id !== pathStart) {
    updateSelection({ pathEnd: d.id })

    const path = findShortestPath(
      pathStart,
      d.id,
      graphData.value.nodes,
      graphData.value.edges
    )

    updatePathResult(path)
    renderer.highlightPath(path)
  } else {
    updateSelection({ pathStart: d.id, pathEnd: null })
    updatePathResult([])
    renderer.clearHighlights()
    renderer.highlightNode(d.id, 'path-start')
  }
}

function handleNeighborModeSelect(d) {
  const hops = graphState.selection.neighborHops || 1
  const neighbors = findNeighbors(d.id, hops, graphData.value.nodes, graphData.value.edges)

  updateNeighborResult(Array.from(neighbors))
  renderer.highlightNeighbors(d.id, neighbors)
}

function closeDetail() {
  selectedNode.value = null
  updateSelection({ nodes: [] })
}

function handleGraphReset() {
  graphData.value = null
  selectedNode.value = null
  searchQuery.value = ''
  activeFilters.value = []
  loadGraphData()
}

async function handleLayoutChange(layoutType) {
  updateLayout(layoutType)
  if (!graphData.value) return

  renderer.stopSimulation()
  isLayoutLoading.value = true

  try {
    if (layoutType === LAYOUT_TYPES.FORCE) {
      renderer.render(graphData.value, renderOptions())
    } else {
      const result = renderer.applyLayout(layoutType, graphData.value, graphState.layoutParams[layoutType])
      if (result?.clustering) {
        updateClustering({ clusterCount: result.clustering.clusterCount })
      }
      renderer.render(graphData.value, renderOptions())
    }
  } finally {
    isLayoutLoading.value = false
  }
}

function handleModeChange(mode) { updateSelection({ mode }) }
function handleClusteringToggle(enabled) { updateClustering({ enabled }) }

function handleVisualModeToggle(enabled) {
  updateVisualMode(enabled ? VISUAL_MODES.TWO_POINT_FIVE_D : VISUAL_MODES.TWO_D)
}

function handleRenderModeChange(mode) {
  updateRenderMode(mode, true)
  if (graphData.value) renderer.render(graphData.value, renderOptions())
}

function handlePerformanceModeToggle(enabled) {
  updatePerformanceMode(enabled)
  if (graphData.value) renderer.render(graphData.value, renderOptions())
}

function handleStatsToggle(show) { showStats.value = show }
function handleMiniMapToggle(show) { showMiniMap.value = show }
function handleMiniMapNavigation({ x, y }) { renderer.panTo({ x, y }) }

function toggleSettings() {
  settingsPanelOpen.value = !settingsPanelOpen.value
}

function closeSettings() {
  settingsPanelOpen.value = false
}

async function handleLayoutChangeFromSettings(newLayout) {
  await handleLayoutChange(newLayout)
}

const entityTypes = computed(() => {
  if (!graphData.value) return []
  return [...new Set(graphData.value.nodes.map(n => n.type).filter(Boolean))]
})

const graphStats = computed(() => ({
  nodeCount: graphData.value?.nodes.length || 0,
  edgeCount: graphData.value?.edges.length || 0,
  clusterCount: 0,
  selectedCount: graphState.selection.nodes.length,
  layout: graphState.layout,
}))

// Bounds for mini-map
const mainViewBounds = computed(() => {
  if (!svgContainer.value) return { x: 0, y: 0, w: 1000, h: 1000 }
  const rect = svgContainer.value.getBoundingClientRect()
  return {
    x: 0,
    y: 0,
    w: rect.width || 1000,
    h: rect.height || 1000,
  }
})

// Current viewport for mini-map — delegates to renderer
const currentViewport = computed(() => renderer.viewport.value)

function toggleFilter(type) {
  const idx = activeFilters.value.indexOf(type)
  if (idx >= 0) activeFilters.value.splice(idx, 1)
  else activeFilters.value.push(type)
}

function applySearchAndFilters() {
  if (!graphData.value) return
  renderer.applySearchFilters(graphData.value, searchQuery.value, activeFilters.value)
}

watch([searchQuery, activeFilters], applySearchAndFilters, { deep: true })

watch(() => graphState.selection.mode, (newMode, oldMode) => {
  if (oldMode === INTERACTION_MODES.LASSO) renderer.teardownLasso()
  if (newMode === INTERACTION_MODES.LASSO && svgContainer.value) {
    nextTick(() => setupLassoEvents())
  }
  if (newMode !== oldMode) renderer.clearHighlights()
})
</script>

<template>
  <!-- Empty state -->
  <div v-if="viewState === 'empty'" class="p-6">
    <EmptyState
      icon="GitBranch"
      title="No knowledge graph"
      description="Upload documents and build a graph to visualize entities and relationships."
      actionLabel="Build Graph"
      @action="startBuild"
    />
  </div>

  <!-- Building state -->
  <div v-else-if="viewState === 'building'" class="p-6">
    <ProgressPanel
      title="Building Knowledge Graph..."
      :steps="GRAPH_BUILD_STEPS"
      :currentStage="store.graphBuildProgress?.stage || ''"
      :progress="{ current: store.graphBuildProgress?.current, total: store.graphBuildProgress?.total }"
      :logEntries="store.graphBuildProgress?.logEntries || []"
      :error="buildError"
      :disconnected="buildDisconnected"
      @cancel="cancelBuild"
      @retry="retryBuild"
    />
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
      @select-layout="handleLayoutChangeFromSettings"
      @toggle-visual-mode="handleVisualModeToggle"
      @toggle-performance-mode="handlePerformanceModeToggle"
      @select-render-mode="handleRenderModeChange"
      @select-interaction-mode="handleModeChange"
      @toggle-stats="handleStatsToggle"
      @toggle-mini-map="handleMiniMapToggle"
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
          <div ref="svgContainer" class="w-full h-full min-h-[500px]" />

          <!-- Stats panel (conditionally rendered in graph area) -->
          <Transition name="fade-in">
            <div v-if="showStats" class="absolute top-3 left-3 z-10">
              <GraphStatsPanel
                v-if="graphData"
                :nodeCount="graphStats.nodeCount"
                :edgeCount="graphStats.edgeCount"
                :clusterCount="graphStats.clusterCount"
                :selectedCount="graphStats.selectedCount"
                :layout="graphStats.layout"
              />
            </div>
          </Transition>

          <!-- Mini-map (conditionally rendered, replaces rebuild button when shown) -->
          <Transition name="fade-in">
            <div v-if="showMiniMap" class="absolute bottom-3 right-3 z-10">
              <GraphMiniMap
                v-if="graphData"
                :nodes="graphData.nodes || []"
                :viewport="currentViewport"
                :mainViewBounds="mainViewBounds"
                @navigate-to="handleMiniMapNavigation"
              />
            </div>
          </Transition>

          <!-- Zoom controls (bottom-left) -->
          <div class="absolute bottom-3 left-3 flex gap-1 z-10">
            <button
              class="w-8 h-8 rounded-md border flex items-center justify-center"
              :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"
              @click="zoomIn"
            >
              <Plus :size="14" />
            </button>
            <button
              class="w-8 h-8 rounded-md border flex items-center justify-center"
              :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"
              @click="zoomOut"
            >
              <Minus :size="14" />
            </button>
            <button
              class="w-8 h-8 rounded-md border flex items-center justify-center"
              :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"
              @click="zoomReset"
            >
              <RotateCcw :size="12" />
            </button>
          </div>

          <!-- Rebuild button (bottom-right, hidden when mini-map shown) -->
          <Transition name="fade-in">
            <div v-if="!showMiniMap" class="absolute bottom-3 right-3 z-10">
              <button
                class="px-3 py-1.5 rounded-md border text-xs"
                :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', color: 'var(--text-secondary)', boxShadow: 'var(--shadow-sm)' }"
                @click="showRebuildModal = true"
              >
                Rebuild Graph
              </button>
            </div>
          </Transition>
        </div>

        <!-- Node detail sidebar (appears when node selected) -->
        <Transition name="slide-in-left">
          <div
            v-if="selectedNode"
            class="w-[260px] border-l shrink-0 overflow-y-auto"
            :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', transition: 'width var(--duration-slow) var(--ease-out)' }"
          >
            <div class="p-4 border-b" :style="{ borderColor: 'var(--border)' }">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: getNodeColor(selectedNode.type) }" />
                  <span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">{{ selectedNode.type }}</span>
                </div>
                <button class="opacity-50 hover:opacity-100 text-xs" @click="closeDetail">✕</button>
              </div>
              <h3 class="text-base font-semibold mt-2" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">{{ selectedNode.id }}</h3>
            </div>
            <div class="p-4">
              <div v-if="selectedNode.description" class="mb-4">
                <p class="text-xs uppercase tracking-wider mb-1" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Description</p>
                <p class="text-sm leading-relaxed" :style="{ color: 'var(--text-secondary)' }">{{ selectedNode.description }}</p>
              </div>
              <div v-if="selectedNode.connections?.length">
                <p class="text-xs uppercase tracking-wider mb-2" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Connected To</p>
                <div class="space-y-1.5">
                  <div
                    v-for="conn in selectedNode.connections"
                    :key="conn.node"
                    class="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer"
                    :style="{ backgroundColor: 'var(--surface-sunken)' }"
                    @click="selectNode({ id: conn.node, type: conn.type })"
                  >
                    <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: getNodeColor(conn.type) }" />
                    <span class="text-sm flex-1" :style="{ color: 'var(--text-primary)' }">{{ conn.node }}</span>
                    <span class="text-xs" :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">{{ conn.label }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Rebuild confirmation modal -->
    <ConfirmModal
      v-if="showRebuildModal"
      title="Rebuild Knowledge Graph?"
      message="This will build a new knowledge graph. Existing simulations keep their original graph data. New simulations will use the rebuilt graph."
      confirmLabel="Rebuild"
      variant="warning"
      @confirm="confirmRebuild"
      @cancel="showRebuildModal = false"
    />
  </GraphErrorBoundary>
</template>

<style scoped>
/* Settings backdrop */
.settings-backdrop {
  position: fixed;
  inset: 53px 0 0 0;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(2px);
  z-index: 40;
}

/* Backdrop fade animation */
.slide-in-right-enter-active .settings-backdrop,
.slide-in-right-leave-active .settings-backdrop {
  transition: opacity 200ms;
}

.slide-in-right-enter-from .settings-backdrop,
.slide-in-right-leave-to .settings-backdrop {
  opacity: 0;
}

/* Fade in animation for conditional elements */
.fade-in-enter-active,
.fade-in-leave-active {
  transition: opacity 200ms, transform 200ms;
}

.fade-in-enter-from,
.fade-in-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* Slide in from left for sidebar */
.slide-in-left-enter-active {
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-in-left-leave-active {
  transition: transform 200ms cubic-bezier(0.4, 0, 1, 1);
}

.slide-in-left-enter-from {
  transform: translateX(-100%);
}

.slide-in-left-leave-to {
  transform: translateX(-100%);
}
</style>
