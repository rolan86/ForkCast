<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import { buildGraph, getGraphData, streamGraphBuild } from '@/api/graphs.js'
import { useGraphState } from '@/composables/useGraphState.js'
import { NEON_COLORS, LAYOUT_TYPES, RENDER_MODES, PERFORMANCE_THRESHOLDS, VISUAL_MODES, INTERACTION_MODES } from '@/constants/graph.js'
import { renderHybrid } from '@/utils/graph/rendering/hybridRenderer.js'
import { runForceLayout, runForceLayoutWithEdgeStrength } from '@/utils/graph/layouts/force.js'
import { runHierarchicalLayout } from '@/utils/graph/layouts/hierarchical.js'
import { runCircularLayout } from '@/utils/graph/layouts/circular.js'
import { runClusteredLayout } from '@/utils/graph/layouts/clustered.js'
import { animateLayoutTransition } from '@/utils/graph/rendering/transition.js'
import { findShortestPath, findNeighbors, findNodesInLasso } from '@/utils/graph/interactions/modes.js'
import EmptyState from '@/components/EmptyState.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import GraphErrorBoundary from '@/components/graph/GraphErrorBoundary.vue'
import GraphTopBar from '@/components/graph/GraphTopBar.vue'
import GraphSettingsPanel from '@/components/graph/GraphSettingsPanel.vue'
import GraphStatsPanel from '@/components/graph/GraphStatsPanel.vue'
import GraphMiniMap from '@/components/graph/GraphMiniMap.vue'
import { Search, Plus, Minus, RotateCcw } from 'lucide-vue-next'
import * as d3 from 'd3'

const route = useRoute()
const store = useProjectStore()
const projectId = computed(() => route.params.id)

// Graph state composable for UI state management
const { graphState, updateLayout, updateSelection, updateView, updateClustering, updateVisualMode, updateRenderMode, updatePerformanceMode, autoSelectRenderMode } = useGraphState()

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

// D3 refs
const svgContainer = ref(null)
let simulation = null
let sseConnection = null
let _zoomBehavior = null
let _svgSelection = null
let _hybridRenderer = null // Hybrid renderer instance

// Lasso selection state
let _lassoPath = null
let _lassoPoints = []
let _isDrawingLasso = false

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
  simulation?.stop()
  _hybridRenderer?.destroy()
})

async function loadGraphData() {
  try {
    graphData.value = await getGraphData(projectId.value)
    viewState.value = 'ready'
    await nextTick()
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

function zoomIn() {
  if (_svgSelection && _zoomBehavior) _svgSelection.transition().duration(300).call(_zoomBehavior.scaleBy, 1.4)
}
function zoomOut() {
  if (_svgSelection && _zoomBehavior) _svgSelection.transition().duration(300).call(_zoomBehavior.scaleBy, 0.7)
}
function zoomReset() {
  if (_svgSelection && _zoomBehavior) _svgSelection.transition().duration(300).call(_zoomBehavior.transform, d3.zoomIdentity)
}

function renderGraph() {
  if (!svgContainer.value || !graphData.value) return

  const container = svgContainer.value
  const width = container.clientWidth
  const height = container.clientHeight || 500

  // DEBUG: Log container dimensions
  console.log('[GraphTab] renderGraph - container dimensions:', {
    clientWidth: container.clientWidth,
    clientHeight: container.clientHeight,
    offsetWidth: container.offsetWidth,
    offsetHeight: container.offsetHeight,
    computedWidth: width,
    computedHeight: height,
    container: container
  })

  // Auto-select render mode based on node count
  const nodeCount = graphData.value.nodes.length
  autoSelectRenderMode(nodeCount)

  // Use hybrid renderer if in hybrid mode
  const shouldUseHybrid = graphState.value.renderMode === RENDER_MODES.HYBRID

  if (shouldUseHybrid) {
    renderGraphHybrid(container, width, height)
  } else {
    renderGraphLegacy(container, width, height)
  }

  // Setup lasso event listeners if in lasso mode
  setupLassoEvents()
}

/**
 * Setup lasso selection event listeners
 */
function setupLassoEvents() {
  if (!svgContainer.value || graphState.value.selection.mode !== INTERACTION_MODES.LASSO) {
    return
  }

  const svg = d3.select(svgContainer.value).select('svg')
  if (svg.empty()) return

  // Remove existing lasso listeners
  svg.on('.lasso', null)

  // Add lasso listeners
  svg
    .on('mousedown.lasso', (event) => {
      // Only start lasso if not clicking on a node
      if (event.target.tagName !== 'circle') {
        startLassoSelection(event)
      }
    })
    .on('mousemove.lasso', (event) => {
      if (_isDrawingLasso) {
        updateLassoSelection(event)
      }
    })
    .on('mouseup.lasso', () => {
      if (_isDrawingLasso) {
        completeLassoSelection()
      }
    })
}

/**
 * Render graph using hybrid renderer (canvas edges + SVG nodes)
 */
function renderGraphHybrid(container, width, height) {
  // DEBUG: Log received dimensions
  console.log('[GraphTab] renderGraphHybrid - dimensions:', { width, height })

  d3.select(container).selectAll('*').remove()

  const nodes = graphData.value.nodes.map(n => ({ ...n }))
  const edges = graphData.value.edges.map(e => ({ ...e }))

  // Set up force simulation with entity-type gravity and connection-based edge strength
  simulation = runForceLayoutWithEdgeStrength(nodes, edges, {
    width,
    height,
    linkDistance: 80, // Base distance, will be adjusted by edge weight
    chargeStrength: -200,
    collideRadius: 8,
    alphaDecay: 0.02,
    velocityDecay: 0.4,
    typeGravity: 0.1, // Enable entity-type gravity (same-type nodes attract)
    centralBias: 0.05, // Enable central bias (high-centrality nodes toward center)
    iterations: 0, // Run continuously for smooth animation
  })

  // Create hybrid renderer
  _hybridRenderer = renderHybrid(
    { nodes, edges },
    container,
    {
      width,
      height,
      onNodeClick: selectNode,
      enableAnimations: true,
    }
  )

  // Link simulation to renderer
  _hybridRenderer.setSimulation(simulation)

  // Update zoom controls
  _svgSelection = _hybridRenderer.nodeSvg
  _zoomBehavior = _hybridRenderer.zoom
}

/**
 * Render graph using legacy SVG/Canvas approach
 * Preserves existing functionality
 */
function renderGraphLegacy(container, width, height) {
  d3.select(container).selectAll('*').remove()

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])

  const g = svg.append('g')
  let currentZoomScale = 1

  const zoom = d3.zoom()
    .scaleExtent([0.3, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
      currentZoomScale = event.transform.k
      g.selectAll('.node-label').attr('display', currentZoomScale > 1.5 ? 'block' : 'none')
    })
  svg.call(zoom)
  _zoomBehavior = zoom
  _svgSelection = svg

  const nodes = graphData.value.nodes.map(n => ({ ...n }))
  const edges = graphData.value.edges.map(e => ({ ...e }))

  _connCounts = {}
  edges.forEach(e => {
    _connCounts[e.source] = (_connCounts[e.source] || 0) + 1
    _connCounts[e.target] = (_connCounts[e.target] || 0) + 1
  })

  function nodeRadius(id) {
    return nodeRadiusFor(id)
  }

  const useCanvas = nodes.length > 150

  if (useCanvas) {
    // Use force layout utility with entity-type gravity and edge strength for canvas rendering
    simulation = runForceLayoutWithEdgeStrength(nodes, edges, {
      width,
      height,
      linkDistance: 80, // Base distance, will be adjusted by edge weight
      chargeStrength: -200,
      collideRadius: 8,
      alphaDecay: 0.02,
      velocityDecay: 0.4,
      typeGravity: 0.1, // Enable entity-type gravity
      centralBias: 0.05, // Enable central bias
      iterations: 300, // Fixed iterations for canvas
    })

    g.selectAll('line')
      .data(edges)
      .join('line')
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1)

    g.selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => nodeRadius(d.id))
      .attr('fill', d => getNodeColor(d.type))
      .attr('opacity', 0.85)
      .on('click', (event, d) => selectNode(d))
  } else {
    // Use force layout utility with entity-type gravity and edge strength for SVG rendering
    simulation = runForceLayoutWithEdgeStrength(nodes, edges, {
      width,
      height,
      linkDistance: 80, // Base distance, will be adjusted by edge weight
      chargeStrength: -200,
      collideRadius: 8,
      alphaDecay: 0.02,
      velocityDecay: 0.4,
      typeGravity: 0.1, // Enable entity-type gravity
      centralBias: 0.05, // Enable central bias
      iterations: 0, // Run continuously for smooth animation
    })

    const link = g.selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1)

    const node = g.selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => nodeRadius(d.id))
      .attr('fill', d => getNodeColor(d.type))
      .attr('opacity', 0.85)
      .attr('cursor', 'pointer')
      .on('click', (event, d) => selectNode(d))
      .call(d3.drag()
        .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })
      )

    node.append('title').text(d => `${d.id} (${d.type})`)

    const labels = g.selectAll('.node-label')
      .data(nodes)
      .join('text')
      .attr('class', 'node-label')
      .attr('display', 'none')
      .attr('font-size', '10px')
      .attr('font-family', 'var(--font-mono)')
      .attr('fill', 'var(--text-primary)')
      .attr('dx', d => nodeRadius(d.id) + 4)
      .attr('dy', 4)
      .text(d => d.id)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      node
        .attr('cx', d => d.x).attr('cy', d => d.y)
      labels
        .attr('x', d => d.x).attr('y', d => d.y)
    })

    node.attr('opacity', 0)
      .transition()
      .delay((d, i) => 500 + i * 20)
      .duration(200)
      .attr('opacity', 0.85)
  }
}

function selectNode(d) {
  const currentMode = graphState.value.selection.mode

  // Handle different interaction modes
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

/**
 * Handle node selection in SELECT mode
 */
function handleSelectMode(d) {
  // Update local selectedNode for sidebar display
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

  // Update composable selection state
  updateSelection({ nodes: [d.id] })
}

/**
 * Handle node selection in PATH mode
 */
function handlePathModeSelect(d) {
  const pathState = {
    start: graphState.value.selection.pathStart,
    end: graphState.value.selection.pathEnd,
  }

  // Determine which node to set
  if (!pathState.start) {
    // Set start node
    updateSelection({ pathStart: d.id })
    // Visual feedback for start node
    highlightNode(d.id, 'path-start')
  } else if (!pathState.end && d.id !== pathState.start) {
    // Set end node and calculate path
    updateSelection({ pathEnd: d.id })

    const path = findShortestPath(
      pathState.start,
      d.id,
      graphData.value.nodes,
      graphData.value.edges
    )

    // Store path for visualization
    graphState.value.selection.pathResult = path

    // Highlight path nodes and edges
    highlightPath(path)
  } else {
    // Reset and start new path
    updateSelection({ pathStart: d.id, pathEnd: null, pathResult: [] })
    clearHighlights()
    highlightNode(d.id, 'path-start')
  }
}

/**
 * Handle node selection in NEIGHBOR mode
 */
function handleNeighborModeSelect(d) {
  const hops = graphState.value.selection.neighborHops || 1
  const neighbors = findNeighbors(d.id, hops, graphData.value.nodes, graphData.value.edges)

  // Store neighbor set for visualization
  graphState.value.selection.neighborResult = Array.from(neighbors)

  // Highlight neighbor nodes
  highlightNeighbors(d.id, neighbors)
}

/**
 * Highlight a specific node
 */
function highlightNode(nodeId, className) {
  if (!svgContainer.value) return
  d3.select(svgContainer.value)
    .selectAll('circle')
    .filter(d => d.id === nodeId)
    .classed(className, true)
}

/**
 * Highlight shortest path
 */
function highlightPath(path) {
  if (!svgContainer.value || !path.length) return

  clearHighlights()

  const pathSet = new Set(path)

  // Highlight path nodes
  d3.select(svgContainer.value)
    .selectAll('circle')
    .filter(d => pathSet.has(d.id))
    .classed('in-path', true)

  // Highlight path edges
  d3.select(svgContainer.value)
    .selectAll('line')
    .filter(d => {
      const source = d.source.id || d.source
      const target = d.target.id || d.target
      return pathSet.has(source) && pathSet.has(target)
    })
    .classed('in-path', true)
}

/**
 * Highlight neighbor nodes
 */
function highlightNeighbors(centerId, neighbors) {
  if (!svgContainer.value) return

  clearHighlights()

  const neighborSet = neighbors

  // Highlight center node
  d3.select(svgContainer.value)
    .selectAll('circle')
    .filter(d => d.id === centerId)
    .classed('neighbor-center', true)

  // Highlight neighbor nodes
  d3.select(svgContainer.value)
    .selectAll('circle')
    .filter(d => neighborSet.has(d.id) && d.id !== centerId)
    .classed('neighbor-highlight', true)
}

/**
 * Clear all highlight classes
 */
function clearHighlights() {
  if (!svgContainer.value) return

  d3.select(svgContainer.value)
    .selectAll('circle')
    .classed('path-start', false)
    .classed('path-end', false)
    .classed('in-path', false)
    .classed('neighbor-center', false)
    .classed('neighbor-highlight', false)

  d3.select(svgContainer.value)
    .selectAll('line')
    .classed('in-path', false)
}

/**
 * Start lasso selection
 */
function startLassoSelection(event) {
  if (graphState.value.selection.mode !== INTERACTION_MODES.LASSO) return

  _isDrawingLasso = true
  _lassoPoints = [[event.x, event.y]]

  // Create lasso path element
  const svg = d3.select(svgContainer.value).select('svg')
  _lassoPath = svg.append('path')
    .attr('class', 'lasso-selection')
    .attr('fill', 'rgba(0, 212, 255, 0.1)')
    .attr('stroke', '#00d4ff')
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '5, 5')

  updateLassoPath()
}

/**
 * Update lasso during drag
 */
function updateLassoSelection(event) {
  if (!_isDrawingLasso) return

  _lassoPoints.push([event.x, event.y])
  updateLassoPath()
}

/**
 * Complete lasso selection
 */
function completeLassoSelection() {
  if (!_isDrawingLasso) return

  _isDrawingLasso = false

  // Find nodes within lasso
  const selectedIds = findNodesInLasso(graphData.value.nodes, _lassoPoints)

  if (selectedIds.length > 0) {
    // Update selection with lasso results (limit to max 50)
    const limitedIds = selectedIds.slice(0, 50)
    updateSelection({ nodes: limitedIds })

    // Highlight selected nodes
    d3.select(svgContainer.value)
      .selectAll('circle')
      .filter(d => limitedIds.includes(d.id))
      .classed('lasso-selected', true)
  }

  // Remove lasso path after a short delay
  setTimeout(() => {
    if (_lassoPath) {
      _lassoPath.remove()
      _lassoPath = null
    }
    _lassoPoints = []
  }, 500)
}

/**
 * Update lasso path visual
 */
function updateLassoPath() {
  if (!_lassoPath || _lassoPoints.length < 2) return

  // Create path string from points
  const pathString = _lassoPoints.map((p, i) => {
    return i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`
  }).join(' ')

  _lassoPath.attr('d', pathString + ' Z') // Close path
}

/**
 * Cancel lasso selection
 */
function cancelLassoSelection() {
  _isDrawingLasso = false

  if (_lassoPath) {
    _lassoPath.remove()
    _lassoPath = null
  }
  _lassoPoints = []

  // Clear lasso selection highlights
  d3.select(svgContainer.value)
    .selectAll('circle')
    .classed('lasso-selected', false)
}

function closeDetail() {
  selectedNode.value = null
  // Clear composable selection state
  updateSelection({ nodes: [] })
}

/**
 * Handle graph reset from error boundary
 */
function handleGraphReset() {
  // Clear graph data and reload
  graphData.value = null
  selectedNode.value = null
  searchQuery.value = ''
  activeFilters.value = []
  loadGraphData()
}

/**
 * Handle layout change from toolbar
 */
function handleLayoutChange(layout) {
  updateLayout(layout)

  if (!graphData.value) return

  // Stop current simulation
  if (simulation) {
    simulation.stop()
  }

  // Apply new layout based on selection
  switch (layout) {
    case LAYOUT_TYPES.HIERARCHICAL:
      applyHierarchicalLayout()
      break
    case LAYOUT_TYPES.CIRCULAR:
      applyCircularLayout()
      break
    case LAYOUT_TYPES.CLUSTERED:
      applyClusteredLayout()
      break
    case LAYOUT_TYPES.FORCE:
    default:
      // Re-render with force layout (default)
      renderGraph()
      break
  }
}

/**
 * Apply hierarchical layout with animation
 */
function applyHierarchicalLayout() {
  if (!svgContainer.value || !graphData.value) return

  const container = svgContainer.value
  const width = container.clientWidth
  const height = container.clientHeight || 500

  const result = runHierarchicalLayout(
    graphData.value.nodes,
    graphData.value.edges,
    { width, height }
  )

  // Update node positions in graphData
  graphData.value.nodes.forEach(node => {
    const positionedNode = result.nodes.find(n => n.id === node.id)
    if (positionedNode) {
      node.x = positionedNode.x
      node.y = positionedNode.y
    }
  })

  // Re-render with new positions
  renderGraph()
}

/**
 * Apply circular layout with animation
 */
function applyCircularLayout() {
  if (!svgContainer.value || !graphData.value) return

  const container = svgContainer.value
  const width = container.clientWidth
  const height = container.clientHeight || 500

  const result = runCircularLayout(
    graphData.value.nodes,
    graphData.value.edges,
    { width, height }
  )

  // Update node positions in graphData
  graphData.value.nodes.forEach(node => {
    const positionedNode = result.nodes.find(n => n.id === node.id)
    if (positionedNode) {
      node.x = positionedNode.x
      node.y = positionedNode.y
    }
  })

  // Re-render with new positions
  renderGraph()
}

/**
 * Apply clustered layout with community detection
 */
function applyClusteredLayout() {
  if (!svgContainer.value || !graphData.value) return

  const container = svgContainer.value
  const width = container.clientWidth
  const height = container.clientHeight || 500

  const result = runClusteredLayout(
    graphData.value.nodes,
    graphData.value.edges,
    { width, height }
  )

  // Update node positions in graphData
  graphData.value.nodes.forEach(node => {
    const positionedNode = result.nodes.find(n => n.id === node.id)
    if (positionedNode) {
      node.x = positionedNode.x
      node.y = positionedNode.y
    }
  })

  // Update clustering state if result includes clustering info
  if (result.clustering) {
    // Update cluster count in stats
    graphStats.value.clusterCount = result.clustering.clusterCount
  }

  // Re-render with new positions
  renderGraph()
}

/**
 * Handle interaction mode change from toolbar
 */
function handleModeChange(mode) {
  updateSelection({ mode })
  console.log('Interaction mode changed to:', mode)
}

/**
 * Handle clustering toggle from toolbar
 */
function handleClusteringToggle() {
  const currentEnabled = graphState.value.clustering.enabled
  updateClustering({ enabled: !currentEnabled })
  console.log('Clustering toggled:', !currentEnabled)
}

/**
 * Handle expand all clusters
 */
function handleExpandAllClusters() {
  // Will be implemented with clustering functionality
  console.log('Expand all clusters')
}

/**
 * Handle collapse all clusters
 */
function handleCollapseAllClusters() {
  // Will be implemented with clustering functionality
  console.log('Collapse all clusters')
}

/**
 * Handle visual mode toggle
 */
function handleVisualModeToggle() {
  const currentMode = graphState.value.visualMode
  updateVisualMode(currentMode === VISUAL_MODES.TWO_POINT_FIVE_D ? VISUAL_MODES.TWO_D : VISUAL_MODES.TWO_POINT_FIVE_D)
}

/**
 * Handle render mode change
 */
function handleRenderModeChange(renderMode) {
  updateRenderMode(renderMode)
  // Re-render graph with new render mode
  if (graphData.value) {
    renderGraph()
  }
}

/**
 * Handle performance mode toggle
 */
function handlePerformanceModeToggle() {
  const currentMode = graphState.value.performance.performanceMode
  updatePerformanceMode(!currentMode)

  // Re-render graph with new performance settings
  if (graphData.value) {
    renderGraph()
  }
}

/**
 * Fit graph to screen
 */
function fitToScreen() {
  if (_svgSelection && _zoomBehavior) {
    _svgSelection.transition().duration(500).call(_zoomBehavior.transform, d3.zoomIdentity)
  }
}

/**
 * Handle mini-map navigation
 */
function handleMiniMapNavigation({ x, y }) {
  if (_svgSelection && _zoomBehavior) {
    _svgSelection.transition().duration(300).call(
      _zoomBehavior.transform,
      d3.zoomIdentity.translate(x, y)
    )
  }
}

/**
 * Toggle settings panel
 */
function toggleSettings() {
  settingsPanelOpen.value = !settingsPanelOpen.value
}

/**
 * Close settings panel
 */
function closeSettings() {
  settingsPanelOpen.value = false
}

/**
 * Handle layout change from settings panel
 */
async function handleLayoutChangeFromSettings(newLayout) {
  isLayoutLoading.value = true
  try {
    await updateLayout(newLayout)
    if (graphData.value) {
      renderGraph()
    }
  } finally {
    isLayoutLoading.value = false
  }
}

/**
 * Handle stats toggle from settings panel
 */
function handleStatsToggle(show) {
  showStats.value = show
}

/**
 * Handle mini-map toggle from settings panel
 */
function handleMiniMapToggle(show) {
  showMiniMap.value = show
}

const entityTypes = computed(() => {
  if (!graphData.value) return []
  return [...new Set(graphData.value.nodes.map(n => n.type).filter(Boolean))]
})

// Stats for GraphStatsPanel
const graphStats = computed(() => ({
  nodeCount: graphData.value?.nodes.length || 0,
  edgeCount: graphData.value?.edges.length || 0,
  clusterCount: 0, // Will be updated when clustering is implemented
  selectedCount: graphState.value.selection.nodes.length,
  layout: graphState.value.layout,
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

// Current viewport for mini-map
const currentViewport = computed(() => {
  if (!_svgSelection || !_zoomBehavior) return { x: 0, y: 0, w: 0, h: 0 }
  // Try to get current transform
  const transform = d3.zoomTransform(_svgSelection.node())
  return {
    x: transform.x,
    y: transform.y,
    w: (mainViewBounds.value.w / transform.k),
    h: (mainViewBounds.value.h / transform.k),
  }
})

function toggleFilter(type) {
  const idx = activeFilters.value.indexOf(type)
  if (idx >= 0) activeFilters.value.splice(idx, 1)
  else activeFilters.value.push(type)
}

// Wire search + filters into D3 visualization
function applySearchAndFilters() {
  if (!svgContainer.value || !graphData.value) return
  const container = d3.select(svgContainer.value)
  const query = searchQuery.value.toLowerCase().trim()
  const filters = activeFilters.value

  container.selectAll('circle').each(function (d) {
    const matchesSearch = !query || d.id.toLowerCase().includes(query) || (d.type || '').toLowerCase().includes(query)
    const matchesFilter = !filters.length || filters.includes(d.type)
    const visible = matchesSearch && matchesFilter
    d3.select(this)
      .attr('opacity', visible ? 0.85 : 0.1)
      .attr('r', visible && query && d.id.toLowerCase().includes(query) ? nodeRadiusFor(d.id) * 1.5 : nodeRadiusFor(d.id))
  })
  container.selectAll('.node-label').each(function (d) {
    const matchesSearch = !query || d.id.toLowerCase().includes(query) || (d.type || '').toLowerCase().includes(query)
    const matchesFilter = !filters.length || filters.includes(d.type)
    d3.select(this).attr('opacity', matchesSearch && matchesFilter ? 1 : 0.1)
  })
  container.selectAll('line').each(function (d) {
    const srcId = d.source.id || d.source
    const tgtId = d.target.id || d.target
    const srcNode = graphData.value.nodes.find(n => n.id === srcId)
    const tgtNode = graphData.value.nodes.find(n => n.id === tgtId)
    const srcMatch = (!query || srcId.toLowerCase().includes(query)) && (!filters.length || filters.includes(srcNode?.type))
    const tgtMatch = (!query || tgtId.toLowerCase().includes(query)) && (!filters.length || filters.includes(tgtNode?.type))
    d3.select(this).attr('opacity', srcMatch || tgtMatch ? 1 : 0.05)
  })
}

// Store nodeRadius function for reuse in search highlighting
let _connCounts = {}
function nodeRadiusFor(id) {
  return 8 + Math.min((_connCounts[id] || 0) * 1.5, 12)
}

watch([searchQuery, activeFilters], applySearchAndFilters, { deep: true })

// Watch for interaction mode changes
watch(() => graphState.value.selection.mode, (newMode, oldMode) => {
  // Cancel any ongoing lasso when leaving lasso mode
  if (oldMode === INTERACTION_MODES.LASSO && _isDrawingLasso) {
    cancelLassoSelection()
  }

  // Setup lasso events when entering lasso mode
  if (newMode === INTERACTION_MODES.LASSO && svgContainer.value) {
    nextTick(() => {
      setupLassoEvents()
    })
  }

  // Clear highlights when switching modes
  if (newMode !== oldMode) {
    clearHighlights()
  }
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
          <div ref="svgContainer" class="w-full h-full" />

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
