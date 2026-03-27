/**
 * Layout Registry and Index
 *
 * Central registry for all layout algorithms.
 * Provides consistent interface for layout selection and execution.
 *
 * @module utils/graph/layouts/index
 */

import { runForceLayout, runForceLayoutWithEdgeStrength } from './force.js'
import { runHierarchicalLayout } from './hierarchical.js'
import { runCircularLayout } from './circular.js'
import { runClusteredLayout } from './clustered.js'
import { LAYOUT_TYPES } from '@/constants/graph.js'

/**
 * Layout registry
 * Maps layout type to layout function and metadata
 */
const layoutRegistry = new Map([
  [LAYOUT_TYPES.FORCE, {
    name: 'Force-Directed',
    description: 'Physics-based simulation with entity-type clustering',
    function: runForceLayoutWithEdgeStrength,
    defaultParams: {
      linkDistance: 80,
      chargeStrength: -200,
      collideRadius: 8,
      alphaDecay: 0.02,
      velocityDecay: 0.4,
      typeGravity: 0.1,
      centralBias: 0.05,
      iterations: 0,
    },
    supportsTransitions: true,
    supportsClustering: true,
    recommendedMaxNodes: 500,
  }],
  [LAYOUT_TYPES.HIERARCHICAL, {
    name: 'Hierarchical',
    description: 'Tree-based layout with root at top',
    function: runHierarchicalLayout,
    defaultParams: {
      nodeWidth: 120,
      nodeHeight: 50,
      levelSpacing: 80,
      siblingSpacing: 30,
      maxRoots: 3,
    },
    supportsTransitions: true,
    supportsClustering: false,
    recommendedMaxNodes: 200,
  }],
  [LAYOUT_TYPES.CIRCULAR, {
    name: 'Circular',
    description: 'Circular arrangement with type-based wedges',
    function: runCircularLayout,
    defaultParams: {
      radius: 300,
      wedgePadding: 0.05,
    },
    supportsTransitions: true,
    supportsClustering: false,
    recommendedMaxNodes: 300,
  }],
  [LAYOUT_TYPES.CLUSTERED, {
    name: 'Clustered',
    description: 'Community-based layout with clusters as groups',
    function: runClusteredLayout,
    defaultParams: {
      clusterArrangement: 'circle',
      minClusterSize: 3,
      maxClusters: 15,
      clusterPadding: 20,
      interClusterDistance: 150,
    },
    supportsTransitions: true,
    supportsClustering: true,
    recommendedMaxNodes: 500,
  }],
])

/**
 * Get layout function by type
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {Function|null} Layout function or null if not found
 */
export function getLayoutFunction(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.function : null
}

/**
 * Get layout metadata by type
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {Object|null} Layout metadata or null if not found
 */
export function getLayoutMetadata(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  if (!layout) return null

  const { function: _, ...metadata } = layout
  return metadata
}

/**
 * Get all registered layout types
 *
 * @returns {Array<string>} Array of layout type identifiers
 */
export function getRegisteredLayouts() {
  return Array.from(layoutRegistry.keys())
}

/**
 * Run a layout by type
 *
 * @param {string} layoutType - Layout type identifier
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {Object} options - Layout options (merged with defaults)
 * @returns {Object} Layout result with positioned nodes
 */
export function runLayout(layoutType, nodes, edges, options = {}) {
  const layout = layoutRegistry.get(layoutType)

  if (!layout) {
    console.warn(`Unknown layout type: ${layoutType}, falling back to force`)
    return runForceLayoutWithEdgeStrength(nodes, edges, options)
  }

  // Merge options with default params
  const mergedOptions = { ...layout.defaultParams, ...options }

  return layout.function(nodes, edges, mergedOptions)
}

/**
 * Check if layout supports transitions
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {boolean} True if layout supports smooth transitions
 */
export function layoutSupportsTransitions(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.supportsTransitions : false
}

/**
 * Check if layout supports clustering
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {boolean} True if layout can use clustering
 */
export function layoutSupportsClustering(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.supportsClustering : false
}

/**
 * Get recommended max nodes for layout
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {number} Recommended maximum node count
 */
export function getLayoutMaxNodes(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.recommendedMaxNodes : 500
}

/**
 * Get best layout for node count
 *
 * @param {number} nodeCount - Number of nodes
 * @returns {string} Recommended layout type
 */
export function getRecommendedLayout(nodeCount) {
  if (nodeCount < 50) {
    return LAYOUT_TYPES.CIRCULAR
  } else if (nodeCount < 200) {
    return LAYOUT_TYPES.HIERARCHICAL
  } else {
    return LAYOUT_TYPES.FORCE
  }
}

/**
 * Register a custom layout
 *
 * @param {string} layoutType - Layout type identifier
 * @param {Object} metadata - Layout metadata
 * @param {Function} layoutFunction - Layout function
 */
export function registerLayout(layoutType, metadata, layoutFunction) {
  layoutRegistry.set(layoutType, {
    ...metadata,
    function: layoutFunction,
  })
}

/**
 * Unregister a layout
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {boolean} True if layout was removed
 */
export function unregisterLayout(layoutType) {
  return layoutRegistry.delete(layoutType)
}

/**
 * Validate layout parameters
 *
 * @param {string} layoutType - Layout type identifier
 * @param {Object} params - Parameters to validate
 * @returns {Object} Validation result {valid, errors}
 */
export function validateLayoutParams(layoutType, params) {
  const layout = layoutRegistry.get(layoutType)

  if (!layout) {
    return { valid: false, errors: [`Unknown layout type: ${layoutType}`] }
  }

  const errors = []

  // Common validations
  if (params.width !== undefined && (params.width <= 0 || params.width > 10000)) {
    errors.push('width must be between 0 and 10000')
  }

  if (params.height !== undefined && (params.height <= 0 || params.height > 10000)) {
    errors.push('height must be between 0 and 10000')
  }

  // Layout-specific validations would go here

  return {
    valid: errors.length === 0,
    errors,
  }
}

/**
 * Get layout display name
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {string} Human-readable layout name
 */
export function getLayoutName(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.name : layoutType
}

/**
 * Get layout description
 *
 * @param {string} layoutType - Layout type identifier
 * @returns {string} Layout description
 */
export function getLayoutDescription(layoutType) {
  const layout = layoutRegistry.get(layoutType)
  return layout ? layout.description : ''
}

// Export layout types for convenience
export { LAYOUT_TYPES }

// Export individual layout functions for direct use
export { runForceLayout, runForceLayoutWithEdgeStrength } from './force.js'
export { runHierarchicalLayout } from './hierarchical.js'
export { runCircularLayout } from './circular.js'
export { runClusteredLayout } from './clustered.js'
