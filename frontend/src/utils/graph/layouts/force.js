/**
 * Force Layout Algorithm
 *
 * Enhanced D3 force-directed layout with:
 * - Entity-type gravity (same-type nodes attract)
 * - Connection-based edge strength
 * - Central node bias (important nodes toward center)
 *
 * @module utils/graph/layouts/force
 */

import * as d3 from 'd3'
import { FORCE_LAYOUT_CONFIG } from '@/constants/graph.js'

/**
 * Run force simulation on graph nodes and edges
 *
 * @param {Array} nodes - Array of node objects with x, y properties
 * @param {Array} edges - Array of edge objects with source, target
 * @param {Object} options - Configuration options
 * @returns {d3.Simulation} D3 force simulation
 */
export function runForceLayout(nodes, edges, options = {}) {
  const {
    width = 800,
    height = 600,
    linkDistance = FORCE_LAYOUT_CONFIG.linkDistance,
    chargeStrength = FORCE_LAYOUT_CONFIG.chargeStrength,
    collideRadius = FORCE_LAYOUT_CONFIG.collideRadius,
    alphaDecay = FORCE_LAYOUT_CONFIG.alphaDecay,
    velocityDecay = 0.4,
    typeGravity = 0.1, // Entity-type gravity strength
    centralBias = 0.05, // Central node pull strength
    iterations = 300, // Simulation iterations (0 = infinite)
  } = options

  // Note: callers are responsible for cloning if they don't want input mutated.
  // useGraphRenderer already clones before calling this function.

  // Calculate connection counts for node radius
  const connCounts = {}
  edges.forEach(e => {
    const sourceId = e.source.id || e.source
    const targetId = e.target.id || e.target
    connCounts[sourceId] = (connCounts[sourceId] || 0) + 1
    connCounts[targetId] = (connCounts[targetId] || 0) + 1
  })

  function nodeRadius(d) {
    return 8 + Math.min((connCounts[d.id] || 0) * 1.5, 12)
  }

  // Calculate node centrality (degree centrality)
  const centrality = {}
  nodes.forEach(n => {
    centrality[n.id] = (connCounts[n.id] || 0)
  })

  const maxCentrality = Math.max(...Object.values(centrality), 1)

  // Create force simulation
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(linkDistance))
    .force('charge', d3.forceManyBody().strength(chargeStrength))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => nodeRadius(d) + collideRadius))

  // Add entity-type gravity if enabled
  if (typeGravity > 0) {
    simulation.force('typeGravity', createTypeGravityForce(nodes, typeGravity))
  }

  // Add central node bias if enabled
  if (centralBias > 0) {
    simulation.force('centralBias', createCentralBiasForce(nodes, centrality, maxCentrality, centralBias))
  }

  // Set simulation parameters
  if (alphaDecay !== undefined) {
    simulation.alphaDecay(alphaDecay)
  }
  if (velocityDecay !== undefined) {
    simulation.velocityDecay(velocityDecay)
  }

  // Run for specified iterations or until convergence
  if (iterations > 0) {
    simulation.stop()
    for (let i = 0; i < iterations; i++) {
      simulation.tick()
    }
  }

  // Clear any fixed positions
  nodes.forEach(node => {
    node.fx = null
    node.fy = null
  })

  return simulation
}

/**
 * Create entity-type gravity force
 * Nodes of the same type attract each other moderately
 *
 * @param {Array} nodes - Simulation nodes
 * @param {number} strength - Gravity strength
 * @returns {Function} D3 force function
 */
function createTypeGravityForce(nodes, strength = 0.1) {
  // Group nodes by type
  const typeGroups = new Map()
  nodes.forEach(node => {
    if (!typeGroups.has(node.type)) {
      typeGroups.set(node.type, [])
    }
    typeGroups.get(node.type).push(node)
  })

  // Calculate centroid for each type
  const typeCentroids = new Map()
  typeGroups.forEach((groupNodes, type) => {
    const x = d3.mean(groupNodes, d => d.x) || 0
    const y = d3.mean(groupNodes, d => d.y) || 0
    typeCentroids.set(type, { x, y })
  })

  return (alpha) => {
    nodes.forEach(node => {
      const centroid = typeCentroids.get(node.type)
      if (centroid) {
        const dx = centroid.x - node.x
        const dy = centroid.y - node.y
        node.vx += dx * strength * alpha
        node.vy += dy * strength * alpha
      }
    })
  }
}

/**
 * Create central bias force
 * Nodes with higher centrality are pulled toward center
 *
 * @param {Array} nodes - Simulation nodes
 * @param {Object} centrality - Node centrality scores
 * @param {number} maxCentrality - Maximum centrality value
 * @param {number} strength - Bias strength
 * @returns {Function} D3 force function
 */
function createCentralBiasForce(nodes, centrality, maxCentrality, strength = 0.05) {
  const centerX = 400 // Will be updated dynamically
  const centerY = 300

  return (alpha) => {
    nodes.forEach(node => {
      const centralityRatio = centrality[node.id] / maxCentrality
      const bias = centralityRatio * strength

      // Pull toward center based on centrality
      node.vx += (centerX - node.x) * bias * alpha
      node.vy += (centerY - node.y) * bias * alpha
    })
  }
}

/**
 * Calculate connection strength for edge
 * Higher weight = shorter edge
 *
 * @param {Object} edge - Edge object
 * @param {number} baseDistance - Base link distance
 * @returns {number} Adjusted distance
 */
export function calculateEdgeDistance(edge, baseDistance = 80) {
  const weight = edge.weight || 1
  // Stronger connections = shorter edges
  return baseDistance / Math.min(weight, 3) // Cap weight effect
}

/**
 * Apply connection-based edge strength to layout
 *
 * @param {Array} edges - Array of edge objects
 * @returns {Array} Edges with calculated distances
 */
export function applyEdgeStrength(edges, baseDistance = 80) {
  return edges.map(edge => ({
    ...edge,
    distance: calculateEdgeDistance(edge, baseDistance),
  }))
}

/**
 * Create force layout with edge strength
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {Object} options - Configuration options
 * @returns {d3.Simulation} D3 force simulation
 */
export function runForceLayoutWithEdgeStrength(nodes, edges, options = {}) {
  const edgesWithStrength = applyEdgeStrength(edges, options.linkDistance || 80)

  return runForceLayout(nodes, edgesWithStrength, {
    ...options,
    // Use calculated distances
    linkDistance: undefined, // Will use edge.distance property
  })
}

/**
 * Calculate node radius based on connections
 *
 * @param {string} nodeId - Node ID
 * @param {Array} edges - Array of edge objects
 * @returns {number} Node radius
 */
export function calculateNodeRadius(nodeId, edges) {
  const connCount = edges.filter(e =>
    (e.source.id || e.source) === nodeId || (e.target.id || e.target) === nodeId
  ).length

  return 8 + Math.min(connCount * 1.5, 12)
}

/**
 * Calculate connection counts for all nodes
 *
 * @param {Array} edges - Array of edge objects
 * @returns {Object} Map of node ID to connection count
 */
export function calculateConnectionCounts(edges) {
  const counts = {}
  edges.forEach(e => {
    const sourceId = e.source.id || e.source
    const targetId = e.target.id || e.target
    counts[sourceId] = (counts[sourceId] || 0) + 1
    counts[targetId] = (counts[targetId] || 0) + 1
  })
  return counts
}

/**
 * Get max/min object values helper
 */
function maxObjectValues(obj) {
  return Math.max(...Object.values(obj))
}
