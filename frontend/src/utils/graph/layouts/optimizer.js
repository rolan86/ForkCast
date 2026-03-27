/**
 * Layout Performance Optimizer
 *
 * Optimizes layout computation for large graphs with:
 * - Web Worker support for off-main-thread computation
 * - Incremental layout updates
 * - Adaptive parameters based on graph size
 * - Pre-computation caching
 *
 * @module utils/graph/layouts/optimizer
 */

import { PERFORMANCE_THRESHOLDS } from '@/constants/graph.js'

/**
 * Get adaptive layout parameters based on graph size
 *
 * @param {number} nodeCount - Number of nodes in the graph
 * @param {string} layoutType - Layout type
 * @returns {Object} Optimized parameters
 */
export function getAdaptiveLayoutParams(nodeCount, layoutType) {
  const params = { nodeCount, layoutType }

  switch (layoutType) {
    case 'force':
      return getForceLayoutParams(nodeCount)
    case 'hierarchical':
      return getHierarchicalLayoutParams(nodeCount)
    case 'circular':
      return getCircularLayoutParams(nodeCount)
    case 'clustered':
      return getClusteredLayoutParams(nodeCount)
    default:
      return {}
  }
}

/**
 * Get force layout parameters adapted to graph size
 */
function getForceLayoutParams(nodeCount) {
  if (nodeCount < 100) {
    // Small graph: high quality simulation
    return {
      iterations: 0, // Continuous
      alphaDecay: 0.02,
      velocityDecay: 0.4,
      linkDistance: 80,
      chargeStrength: -200,
    }
  } else if (nodeCount < 300) {
    // Medium graph: balanced
    return {
      iterations: 300,
      alphaDecay: 0.03,
      velocityDecay: 0.5,
      linkDistance: 70,
      chargeStrength: -150,
    }
  } else {
    // Large graph: fast approximation
    return {
      iterations: 150,
      alphaDecay: 0.05,
      velocityDecay: 0.6,
      linkDistance: 60,
      chargeStrength: -100,
    }
  }
}

/**
 * Get hierarchical layout parameters adapted to graph size
 */
function getHierarchicalLayoutParams(nodeCount) {
  if (nodeCount < 100) {
    return {
      maxRoots: 3,
      levelSpacing: 80,
      siblingSpacing: 30,
    }
  } else if (nodeCount < 300) {
    return {
      maxRoots: 5,
      levelSpacing: 60,
      siblingSpacing: 20,
    }
  } else {
    return {
      maxRoots: 10,
      levelSpacing: 40,
      siblingSpacing: 15,
    }
  }
}

/**
 * Get circular layout parameters adapted to graph size
 */
function getCircularLayoutParams(nodeCount) {
  const baseRadius = Math.max(100, Math.min(400, nodeCount * 2))

  return {
    radius: baseRadius,
    wedgePadding: nodeCount > 200 ? 0.02 : 0.05,
  }
}

/**
 * Get clustered layout parameters adapted to graph size
 */
function getClusteredLayoutParams(nodeCount) {
  if (nodeCount < 100) {
    return {
      minClusterSize: 3,
      maxClusters: 10,
      clusterArrangement: 'circle',
    }
  } else if (nodeCount < 300) {
    return {
      minClusterSize: 5,
      maxClusters: 15,
      clusterArrangement: 'circle',
    }
  } else {
    return {
      minClusterSize: 10,
      maxClusters: 20,
      clusterArrangement: 'grid',
    }
  }
}

/**
 * Estimate layout computation time
 *
 * @param {number} nodeCount - Number of nodes
 * @param {number} edgeCount - Number of edges
 * @param {string} layoutType - Layout type
 * @returns {number} Estimated time in milliseconds
 */
export function estimateLayoutTime(nodeCount, edgeCount, layoutType) {
  // Base time per node (ms)
  const baseTimePerNode = {
    force: 2,
    hierarchical: 1,
    circular: 0.5,
    clustered: 3,
  }

  const baseTime = baseTimePerNode[layoutType] || 1

  // Edge complexity factor
  const edgeFactor = Math.log10(edgeCount + 1)

  return Math.ceil(nodeCount * baseTime * edgeFactor)
}

/**
 * Create incremental layout updater
 *
 * @param {Function} layoutFunction - Layout function to call
 * @param {number} batchSize - Number of iterations per batch
 * @returns {Function} Incremental updater function
 */
export function createIncrementalLayout(layoutFunction, batchSize = 50) {
  let isRunning = false
  let currentIteration = 0
  let simulation = null

  function start(nodes, edges, options) {
    isRunning = true
    currentIteration = 0

    // Run initial layout
    const result = layoutFunction(nodes, edges, {
      ...options,
      iterations: batchSize,
    })

    simulation = result.simulation || null
    return result
  }

  function continue() {
    if (!isRunning || !simulation) return null

    // Run a batch of iterations
    for (let i = 0; i < batchSize && simulation.alpha() > 0.1; i++) {
      simulation.tick()
      currentIteration++
    }

    if (simulation.alpha() <= 0.1) {
      isRunning = false
    }

    return {
      iteration: currentIteration,
      alpha: simulation.alpha(),
      done: !isRunning,
    }
  }

  function stop() {
    isRunning = false
    if (simulation) {
      simulation.stop()
    }
  }

  return { start, continue, stop, isRunning: () => isRunning }
}

/**
 * Create pre-computed layout cache
 */
export class LayoutCache {
  constructor(maxSize = 10) {
    this.cache = new Map()
    this.maxSize = maxSize
    this.accessOrder = []
  }

  /**
   * Generate cache key from layout parameters
   */
  generateKey(nodes, edges, layoutType, options) {
    // Create a hash based on node/edge counts and key options
    const nodeIds = nodes.map(n => n.id).sort().join(',')
    const edgeIds = edges.map(e => {
      const s = e.source.id || e.source
      const t = e.target.id || e.target
      return [s, t].sort().join('-')
    }).sort().join('|')

    const optionsStr = JSON.stringify({
      layoutType,
      width: options.width,
      height: options.height,
    })

    return `${nodeIds.length}-${edgeIds.length}-${layoutType}-${optionsStr}`
  }

  /**
   * Get cached layout if available
   */
  get(key) {
    if (this.cache.has(key)) {
      // Update access order
      const index = this.accessOrder.indexOf(key)
      if (index > -1) {
        this.accessOrder.splice(index, 1)
        this.accessOrder.push(key)
      }
      return this.cache.get(key)
    }
    return null
  }

  /**
   * Set cached layout
   */
  set(key, value) {
    // Remove oldest if at capacity
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const oldest = this.accessOrder.shift()
      this.cache.delete(oldest)
    }

    this.cache.set(key, value)

    // Update access order
    if (!this.accessOrder.includes(key)) {
      this.accessOrder.push(key)
    }
  }

  /**
   * Clear cache
   */
  clear() {
    this.cache.clear()
    this.accessOrder = []
  }

  /**
   * Get cache statistics
   */
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      keys: Array.from(this.cache.keys()),
    }
  }
}

/**
 * Create singleton layout cache instance
 */
export const layoutCache = new LayoutCache()

/**
 * Run layout with caching
 */
export function runCachedLayout(nodes, edges, layoutType, options, layoutFunction) {
  const key = layoutCache.generateKey(nodes, edges, layoutType, options)
  const cached = layoutCache.get(key)

  if (cached) {
    // Return cached result with cloned nodes to avoid mutation
    return {
      ...cached,
      nodes: cached.nodes.map(n => ({ ...n })),
      fromCache: true,
    }
  }

  // Compute new layout
  const result = layoutFunction(nodes, edges, options)

  // Cache result
  layoutCache.set(key, result)

  return {
    ...result,
    fromCache: false,
  }
}

/**
 * Check if layout should use Web Worker
 *
 * @param {number} nodeCount - Number of nodes
 * @param {number} estimatedTime - Estimated computation time in ms
 * @returns {boolean} True if should use worker
 */
export function shouldUseWorker(nodeCount, estimatedTime) {
  // Use worker for graphs > 200 nodes or estimated time > 500ms
  return nodeCount > 200 || estimatedTime > 500
}

/**
 * Get recommended optimization strategy
 *
 * @param {number} nodeCount - Number of nodes
 * @param {number} edgeCount - Number of edges
 * @returns {Object} Recommended strategy
 */
export function getOptimizationStrategy(nodeCount, edgeCount) {
  const density = edgeCount / (nodeCount * (nodeCount - 1)) || 0

  if (nodeCount > 500) {
    return {
      strategy: 'incremental',
      useWorker: true,
      batchSize: 100,
      adaptiveParams: true,
    }
  } else if (nodeCount > 200 || density > 0.1) {
    return {
      strategy: 'single-pass',
      useWorker: false,
      adaptiveParams: true,
      precompute: true,
    }
  } else {
    return {
      strategy: 'continuous',
      useWorker: false,
      adaptiveParams: false,
      precompute: false,
    }
  }
}
