/**
 * useGraphState Composable
 *
 * Manages local UI state for the graph visualization.
 * Works alongside useProjectStore which manages persistent graph data.
 *
 * State managed here:
 * - Layout preferences and current layout
 * - Visual mode (2D vs 2.5D)
 * - Clustering state
 * - Selection state
 * - View transform (zoom, pan)
 *
 * @composable
 */

import { reactive, readonly, computed } from 'vue'
import {
  LAYOUT_TYPES,
  VISUAL_MODES,
  RENDER_MODES,
  INTERACTION_MODES,
  PERFORMANCE_THRESHOLDS,
  CONNECTION_STYLES,
  PERFORMANCE_PRESETS,
} from '@/constants/graph.js'

/**
 * Load saved layout preference from localStorage
 * @returns {string|null} Saved layout type or null
 */
function loadSavedLayout() {
  try {
    const saved = localStorage.getItem('graph-layout-preference')
    if (saved && Object.values(LAYOUT_TYPES).includes(saved)) {
      return saved
    }
  } catch {
    // Ignore localStorage errors
  }
  return null
}

/**
 * Load saved layout parameters from localStorage
 * @returns {Object} Saved layout parameters
 */
function loadSavedLayoutParams() {
  try {
    const saved = localStorage.getItem('graph-layout-params')
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore localStorage errors
  }
  return {}
}

const INTERACTION_META = {
  select: { cursor: 'pointer', instruction: null },
  path: { cursor: 'crosshair', instruction: 'Click two nodes to find shortest path' },
  neighbor: { cursor: 'cell', instruction: 'Click a node to highlight its neighbors' },
  lasso: { cursor: 'crosshair', instruction: 'Click and drag to select multiple nodes' },
}

/**
 * Create a reactive state object for graph UI
 * All state updates should use the provided mutator functions
 * to maintain reactivity and enable change tracking
 */
function createInitialState() {
  const savedLayout = loadSavedLayout()
  const savedParams = loadSavedLayoutParams()

  return {
    // Layout configuration (load saved preference if available)
    layout: savedLayout || LAYOUT_TYPES.FORCE,
    visualMode: VISUAL_MODES.TWO_POINT_FIVE_D,
    renderMode: RENDER_MODES.HYBRID,

    // Layout parameters (configurable per layout, merge with saved params)
    layoutParams: {
      [LAYOUT_TYPES.FORCE]: {
        linkDistance: 80,
        chargeStrength: -200,
        collideRadius: 8,
        ...savedParams[LAYOUT_TYPES.FORCE],
      },
      [LAYOUT_TYPES.HIERARCHICAL]: {
        levelSpacing: 100,
        siblingSpacing: 60,
        ...savedParams[LAYOUT_TYPES.HIERARCHICAL],
      },
      [LAYOUT_TYPES.CIRCULAR]: {
        radius: 200,
        startAngle: 0,
        ...savedParams[LAYOUT_TYPES.CIRCULAR],
      },
      [LAYOUT_TYPES.CLUSTERED]: {
        clusterPadding: 20,
        interClusterDistance: 150,
        ...savedParams[LAYOUT_TYPES.CLUSTERED],
      },
    },

    // Clustering state
    clustering: {
      enabled: false,
      autoDetect: true,
      expandedClusters: new Set(), // Set of cluster IDs that are expanded
    },

    // Selection state
    selection: {
      nodes: [], // Array of selected node IDs (max 10 for multi-select)
      mode: INTERACTION_MODES.SELECT, // Current interaction mode
      pathStart: null, // First node selected in path mode
      pathEnd: null, // Second node selected in path mode
      neighborHops: 1, // Hop distance for neighbor mode
      pathResult: [],       // Array of node IDs in shortest path
      neighborResult: [],   // Array of node IDs in neighbor set
    },

    // View transform state
    view: {
      zoom: 1,
      pan: { x: 0, y: 0 },
      viewport: { x: 0, y: 0, w: 0, h: 0 }, // Current viewport bounds
    },

    // Performance mode
    performance: {
      animationsEnabled: true,
      performanceMode: false, // When true, reduces effects for better FPS
      fps: 60, // Current FPS (dev mode only)
    },

    // 3D-specific settings
    settings3d: {
      connectionStyle: CONNECTION_STYLES.CURVED,
      glowEnabled: true,
      pulseEnabled: true,
      autoRotate: false,
      performancePreset: 'quality',
    },

    // Track whether user manually selected render mode
    _userSelectedRenderMode: false,
  }
}

/**
 * Graph state composable
 * @returns {Object} Graph state and mutator functions
 */
export function useGraphState() {
  const state = reactive(createInitialState())

  /**
   * Computed property for accessing graph state
   * Read-only access to prevent direct mutation
   */
  const graphState = readonly(state)

  const interactionMeta = computed(() =>
    INTERACTION_META[state.selection.mode] || INTERACTION_META.select
  )

  /**
   * Update the current layout algorithm
   * @param {string} layoutType - One of LAYOUT_TYPES
   */
  function updateLayout(layoutType) {
    if (Object.values(LAYOUT_TYPES).includes(layoutType)) {
      state.layout = layoutType
      // Persist preference
      try {
        localStorage.setItem('graph-layout-preference', layoutType)
      } catch {
        // Ignore localStorage errors
      }
    }
  }

  /**
   * Update a specific layout parameter
   * @param {string} layoutType - Layout to update
   * @param {string} param - Parameter name
   * @param {*} value - New value
   */
  function updateLayoutParam(layoutType, param, value) {
    if (state.layoutParams[layoutType]) {
      state.layoutParams[layoutType][param] = value
      // Persist parameters to localStorage
      try {
        localStorage.setItem('graph-layout-params', JSON.stringify(state.layoutParams))
      } catch {
        // Ignore localStorage errors
      }
    }
  }

  /**
   * Update visual mode (2D vs 2.5D)
   * @param {string} visualMode - One of VISUAL_MODES
   */
  function updateVisualMode(visualMode) {
    if (Object.values(VISUAL_MODES).includes(visualMode)) {
      state.visualMode = visualMode
    }
  }

  /**
   * Update render mode (SVG, Canvas, Hybrid)
   * @param {string} renderMode - One of RENDER_MODES
   * @param {boolean} isUserSelection - Whether user manually selected the mode
   */
  function updateRenderMode(renderMode, isUserSelection = false) {
    if (Object.values(RENDER_MODES).includes(renderMode)) {
      state.renderMode = renderMode
      state._userSelectedRenderMode = isUserSelection
    }
  }

  /**
   * Update clustering state
   * @param {Object} updates - Partial clustering state updates
   */
  function updateClustering(updates) {
    Object.assign(state.clustering, updates)
  }

  /**
   * Toggle cluster expansion
   * @param {string} clusterId - Cluster ID to toggle
   */
  function toggleCluster(clusterId) {
    if (state.clustering.expandedClusters.has(clusterId)) {
      state.clustering.expandedClusters.delete(clusterId)
    } else {
      state.clustering.expandedClusters.add(clusterId)
    }
  }

  /**
   * Update selection state
   * Uses immutable array updates for proper Vue reactivity
   * @param {Object} updates - Partial selection state updates
   */
  function updateSelection(updates) {
    if (updates.nodes !== undefined) {
      // Ensure nodes is always an array (immutable update)
      state.selection.nodes = Array.isArray(updates.nodes)
        ? [...updates.nodes]
        : [updates.nodes]
    }

    if (updates.mode !== undefined) {
      state.selection.mode = updates.mode
    }

    if (updates.pathStart !== undefined) {
      state.selection.pathStart = updates.pathStart
    }

    if (updates.pathEnd !== undefined) {
      state.selection.pathEnd = updates.pathEnd
    }

    if (updates.neighborHops !== undefined) {
      state.selection.neighborHops = updates.neighborHops
    }
  }

  /**
   * Add a node to the current selection
   * @param {string} nodeId - Node ID to add
   */
  function addNodeToSelection(nodeId) {
    if (!state.selection.nodes.includes(nodeId)) {
      if (state.selection.nodes.length < 10) {
        state.selection.nodes = [...state.selection.nodes, nodeId]
      }
    }
  }

  /**
   * Remove a node from the current selection
   * @param {string} nodeId - Node ID to remove
   */
  function removeNodeFromSelection(nodeId) {
    state.selection.nodes = state.selection.nodes.filter(id => id !== nodeId)
  }

  /**
   * Clear all selected nodes
   */
  function clearSelection() {
    state.selection.nodes = []
    state.selection.pathStart = null
    state.selection.pathEnd = null
  }

  /**
   * Update view transform (zoom/pan)
   * @param {Object} updates - Partial view state updates
   */
  function updateView(updates) {
    if (updates.zoom !== undefined) {
      state.view.zoom = updates.zoom
    }

    if (updates.pan !== undefined) {
      state.view.pan = { ...state.view.pan, ...updates.pan }
    }

    if (updates.viewport !== undefined) {
      state.view.viewport = { ...state.view.viewport, ...updates.viewport }
    }
  }

  /**
   * Update performance mode
   * @param {boolean} enabled - Whether performance mode is enabled
   */
  function updatePerformanceMode(enabled) {
    state.performance.performanceMode = enabled
    state.performance.animationsEnabled = !enabled
  }

  /**
   * Update 3D-specific settings
   * @param {Object} updates - Partial 3D settings updates
   */
  function update3DSettings(updates) {
    Object.assign(state.settings3d, updates)
  }

  /**
   * Apply a performance preset for 3D rendering
   * @param {string} presetName - Name of preset (quality, balanced, performance)
   */
  function applyPerformancePreset(presetName) {
    const preset = PERFORMANCE_PRESETS[presetName.toUpperCase()]
    if (!preset) return
    state.settings3d.glowEnabled = preset.glow
    state.settings3d.pulseEnabled = preset.pulse
    state.settings3d.connectionStyle = preset.connectionStyle
    state.settings3d.performancePreset = presetName
  }

  function updatePathResult(path) {
    state.selection.pathResult = Array.isArray(path) ? [...path] : []
  }

  function updateNeighborResult(neighbors) {
    state.selection.neighborResult = Array.isArray(neighbors) ? [...neighbors] : []
  }

  /**
   * Reset state to initial values
   * Useful for cleanup or testing
   */
  function reset() {
    const initialState = createInitialState()
    Object.assign(state, initialState)
  }

  /**
   * Load persisted preferences from localStorage
   */
  function loadPersistedPreferences() {
    try {
      const savedLayout = localStorage.getItem('graph-layout-preference')
      if (savedLayout && Object.values(LAYOUT_TYPES).includes(savedLayout)) {
        state.layout = savedLayout
      }
    } catch {
      // Ignore localStorage errors
    }
  }

  // Load persisted preferences on initialization
  loadPersistedPreferences()

  return {
    // State access (readonly)
    graphState,
    interactionMeta,

    // Layout mutators
    updateLayout,
    updateLayoutParam,
    updateVisualMode,
    updateRenderMode,
    // Clustering mutators
    updateClustering,
    toggleCluster,

    // Selection mutators
    updateSelection,
    addNodeToSelection,
    removeNodeFromSelection,
    clearSelection,
    updatePathResult,
    updateNeighborResult,

    // View mutators
    updateView,

    // Performance mutators
    updatePerformanceMode,
    update3DSettings,
    applyPerformancePreset,

    // Utilities
    reset,
    loadPersistedPreferences,
  }
}
