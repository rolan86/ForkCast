/**
 * Circular Layout Algorithm
 *
 * Arranges nodes in a circle with entity-type-based wedges.
 * Nodes of same type grouped together, positioned by connection strength.
 *
 * @module utils/graph/layouts/circular
 */

import { CIRCULAR_LAYOUT_CONFIG } from '@/constants/graph.js'

/**
 * Calculate angle for a node within its type wedge
 *
 * @param {string} nodeId - Node ID
 * @param {Array} sameTypeNodes - All nodes of same type
 * @param {Object} connectionCounts - Node ID to connection count
 * @param {number} startAngle - Start angle of wedge
 * @param {number} endAngle - End angle of wedge
 * @returns {number} Angle in radians
 */
function calculateNodeAngle(nodeId, sameTypeNodes, connectionCounts, startAngle, endAngle) {
  const nodeIndex = sameTypeNodes.findIndex(n => n.id === nodeId)
  const nodeCount = sameTypeNodes.length

  if (nodeCount === 1) {
    return (startAngle + endAngle) / 2
  }

  // Sort nodes by connection count (highest first)
  const sortedNodes = [...sameTypeNodes].sort((a, b) => {
    const countA = connectionCounts[a.id] || 0
    const countB = connectionCounts[b.id] || 0
    return countB - countA
  })

  const sortedIndex = sortedNodes.findIndex(n => n.id === nodeId)
  const wedgeSize = endAngle - startAngle

  // Position within wedge based on sorted index
  return startAngle + (sortedIndex / (nodeCount - 1)) * wedgeSize
}

/**
 * Calculate connection counts for all nodes
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @returns {Object} Map of node ID to connection count
 */
function calculateConnectionCounts(nodes, edges) {
  const counts = {}
  nodes.forEach(n => counts[n.id] = 0)

  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target
    counts[source] = (counts[source] || 0) + 1
    counts[target] = (counts[target] || 0) + 1
  })

  return counts
}

/**
 * Group nodes by entity type
 *
 * @param {Array} nodes - Array of node objects
 * @returns {Map} Map of type to array of nodes
 */
function groupNodesByType(nodes) {
  const typeGroups = new Map()

  nodes.forEach(node => {
    const type = node.type || 'Unknown'
    if (!typeGroups.has(type)) {
      typeGroups.set(type, [])
    }
    typeGroups.get(type).push(node)
  })

  return typeGroups
}

/**
 * Calculate wedge angles for each type
 *
 * @param {Map} typeGroups - Map of type to array of nodes
 * @param {number} totalNodes - Total number of nodes
 * @param {number} wedgePadding - Padding between wedges (radians)
 * @returns {Map} Map of type to {startAngle, endAngle}
 */
function calculateTypeWedges(typeGroups, totalNodes, wedgePadding = 0.05) {
  const wedges = new Map()
  const numTypes = typeGroups.size

  if (numTypes === 0) return wedges

  // Calculate wedge size for each type based on node count
  let currentAngle = 0

  typeGroups.forEach((nodes, type) => {
    const typeRatio = nodes.length / totalNodes
    const wedgeSize = typeRatio * (2 * Math.PI - numTypes * wedgePadding)

    wedges.set(type, {
      startAngle: currentAngle,
      endAngle: currentAngle + wedgeSize,
    })

    currentAngle += wedgeSize + wedgePadding
  })

  return wedges
}

/**
 * Run circular layout on graph nodes and edges
 *
 * @param {Array} nodes - Array of node objects with x, y properties
 * @param {Array} edges - Array of edge objects with source, target
 * @param {Object} options - Configuration options
 * @returns {Object} Layout result with positioned nodes
 */
export function runCircularLayout(nodes, edges, options = {}) {
  const {
    width = 800,
    height = 600,
    radius = CIRCULAR_LAYOUT_CONFIG.radius,
    wedgePadding = CIRCULAR_LAYOUT_CONFIG.wedgePadding,
  } = options

  if (!nodes.length) {
    return { nodes: [], edges }
  }

  // Clone nodes to avoid mutating input
  const layoutNodes = nodes.map(n => ({ ...n }))

  // Handle small number of nodes (< 5) - arrange in small circle
  if (nodes.length < 5) {
    return arrangeInSmallCircle(layoutNodes, width, height)
  }

  // Group nodes by type
  const typeGroups = groupNodesByType(nodes)
  const connectionCounts = calculateConnectionCounts(nodes, edges)

  // Calculate wedge angles for each type
  const wedges = calculateTypeWedges(typeGroups, nodes.length, wedgePadding)

  // Calculate center
  const centerX = width / 2
  const centerY = height / 2

  // Adjust radius based on node count to prevent overlap
  const adjustedRadius = Math.min(radius, Math.min(width, height) / 2 - 50)

  // Position each node
  typeGroups.forEach((typeNodes, type) => {
    const wedge = wedges.get(type)
    if (!wedge) return

    typeNodes.forEach(node => {
      const angle = calculateNodeAngle(
        node.id,
        typeNodes,
        connectionCounts,
        wedge.startAngle,
        wedge.endAngle
      )

      const layoutNode = layoutNodes.find(n => n.id === node.id)
      if (layoutNode) {
        layoutNode.x = centerX + adjustedRadius * Math.cos(angle)
        layoutNode.y = centerY + adjustedRadius * Math.sin(angle)
      }
    })
  })

  return { nodes: layoutNodes, edges }
}

/**
 * Arrange small number of nodes in a circle
 *
 * @param {Array} nodes - Array of node objects
 * @param {number} width - Container width
 * @param {number} height - Container height
 * @returns {Object} Layout result with positioned nodes
 */
function arrangeInSmallCircle(nodes, width, height) {
  const centerX = width / 2
  const centerY = height / 2
  const radius = Math.min(width, height) / 3

  nodes.forEach((node, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI
    node.x = centerX + radius * Math.cos(angle)
    node.y = centerY + radius * Math.sin(angle)
  })

  return { nodes, edges: [] }
}

/**
 * Get type wedge boundaries for visualization
 *
 * @param {Array} nodes - Array of node objects
 * @param {Object} options - Layout options
 * @returns {Array} Array of {type, startAngle, endAngle, color}
 */
export function getTypeWedges(nodes, options = {}) {
  const typeGroups = groupNodesByType(nodes)
  const wedges = calculateTypeWedges(typeGroups, nodes.length, options.wedgePadding)

  return Array.from(wedges.entries()).map(([type, angles]) => ({
    type,
    startAngle: angles.startAngle,
    endAngle: angles.endAngle,
  }))
}

/**
 * Calculate optimal radius for circular layout
 *
 * @param {number} nodeCount - Number of nodes
 * @param {number} nodeSize - Size of each node
 * @returns {number} Optimal radius
 */
export function calculateOptimalRadius(nodeCount, nodeSize = 20) {
  const circumference = nodeCount * nodeSize * 1.5 // 1.5x for spacing
  return circumference / (2 * Math.PI)
}

/**
 * Get node order by type for circular layout
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @returns {Array} Ordered array of nodes by type and connection count
 */
export function getNodesByTypeOrder(nodes, edges) {
  const connectionCounts = calculateConnectionCounts(nodes, edges)
  const typeGroups = groupNodesByType(nodes)

  const orderedNodes = []

  // Sort types by name for consistent ordering
  const sortedTypes = Array.from(typeGroups.keys()).sort()

  sortedTypes.forEach(type => {
    const typeNodes = typeGroups.get(type) || []
    // Sort by connection count (highest first)
    const sortedNodes = [...typeNodes].sort((a, b) => {
      const countA = connectionCounts[a.id] || 0
      const countB = connectionCounts[b.id] || 0
      return countB - countA
    })
    orderedNodes.push(...sortedNodes)
  })

  return orderedNodes
}
