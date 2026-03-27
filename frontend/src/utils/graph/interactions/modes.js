/**
 * Graph Interaction Modes
 *
 * Handles different interaction modes for the graph visualization:
 * - Select: Single/multi-select nodes
 * - Path: Find shortest path between nodes
 * - Neighbor: Highlight N-hop neighbors
 * - Lasso: Drag to select multiple nodes
 *
 * @module utils/graph/interactions/modes
 */

import { INTERACTION_MODES } from '@/constants/graph.js'

/**
 * Find shortest path between two nodes using BFS
 *
 * @param {string} startNodeId - Starting node ID
 * @param {string} endNodeId - Ending node ID
 * @param {Array} nodes - All nodes
 * @param {Array} edges - All edges
 * @returns {Array} Array of node IDs in the path (inclusive)
 */
export function findShortestPath(startNodeId, endNodeId, nodes, edges) {
  if (startNodeId === endNodeId) {
    return [startNodeId]
  }

  // Build adjacency list
  const adjacency = new Map()
  nodes.forEach(n => adjacency.set(n.id, []))
  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target
    adjacency.get(source)?.push(target)
    adjacency.get(target)?.push(source)
  })

  // BFS to find shortest path
  const queue = [[startNodeId]]
  const visited = new Set([startNodeId])

  while (queue.length > 0) {
    const path = queue.shift()
    const node = path[path.length - 1]

    if (node === endNodeId) {
      return path
    }

    const neighbors = adjacency.get(node) || []
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        queue.push([...path, neighbor])
      }
    }
  }

  return [] // No path found
}

/**
 * Find N-hop neighbors of a node
 *
 * @param {string} nodeId - Center node ID
 * @param {number} hops - Number of hops to include
 * @param {Array} nodes - All nodes
 * @param {Array} edges - All edges
 * @returns {Set} Set of node IDs in the neighborhood
 */
export function findNeighbors(nodeId, hops, nodes, edges) {
  if (hops < 1) return new Set([nodeId])

  // Build adjacency list
  const adjacency = new Map()
  nodes.forEach(n => adjacency.set(n.id, []))
  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target
    adjacency.get(source)?.push(target)
    adjacency.get(target)?.push(source)
  })

  // BFS to find neighbors within N hops
  const result = new Set([nodeId])
  const currentLevel = new Set([nodeId])

  for (let h = 0; h < hops; h++) {
    const nextLevel = new Set()

    currentLevel.forEach(nodeId => {
      const neighbors = adjacency.get(nodeId) || []
      neighbors.forEach(neighbor => {
        if (!result.has(neighbor)) {
          result.add(neighbor)
          nextLevel.add(neighbor)
        }
      })
    })

    currentLevel.clear()
    nextLevel.forEach(id => currentLevel.add(id))

    if (currentLevel.size === 0) break
  }

  return result
}

/**
 * Find common connections between two nodes
 *
 * @param {string} nodeId1 - First node ID
 * @param {string} nodeId2 - Second node ID
 * @param {Array} edges - All edges
 * @returns {Array} Array of node IDs that connect to both nodes
 */
export function findCommonConnections(nodeId1, nodeId2, edges) {
  const connections1 = new Set()
  const connections2 = new Set()

  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target

    if (source === nodeId1) connections1.add(target)
    if (target === nodeId1) connections1.add(source)
    if (source === nodeId2) connections2.add(target)
    if (target === nodeId2) connections2.add(source)
  })

  return Array.from(connections1).filter(id => connections2.has(id))
}

/**
 * Show subgraph centered on a node
 *
 * @param {string} centerNodeId - Center node ID
 * @param {number} radius - Number of hops to include
 * @param {Array} nodes - All nodes
 * @param {Array} edges - All edges
 * @returns {Object} Subgraph with filtered nodes and edges
 */
export function extractSubgraph(centerNodeId, radius, nodes, edges) {
  const neighborIds = findNeighbors(centerNodeId, radius, nodes, edges)
  const neighborIdSet = new Set(neighborIds)

  const subgraphNodes = nodes.filter(n => neighborIdSet.has(n.id))
  const subgraphEdges = edges.filter(e => {
    const source = e.source.id || e.source
    const target = e.target.id || e.target
    return neighborIdSet.has(source) && neighborIdSet.has(target)
  })

  return {
    nodes: subgraphNodes,
    edges: subgraphEdges,
    centerNodeId,
  }
}

/**
 * Handle node click in select mode
 *
 * @param {string} nodeId - Clicked node ID
 * @param {Array} currentSelection - Currently selected node IDs
 * @param {boolean} multiSelect - Whether multi-select is active
 * @param {number} maxSelection - Maximum number of nodes that can be selected
 * @returns {Array} New selection array
 */
export function handleSelectClick(nodeId, currentSelection, multiSelect = false, maxSelection = 10) {
  if (multiSelect) {
    if (currentSelection.includes(nodeId)) {
      // Remove from selection
      return currentSelection.filter(id => id !== nodeId)
    } else {
      // Add to selection if under limit
      if (currentSelection.length < maxSelection) {
        return [...currentSelection, nodeId]
      }
      return currentSelection // At limit, don't add
    }
  } else {
    // Single select: replace selection
    return [nodeId]
  }
}

/**
 * Check if nodes are within lasso selection bounds
 *
 * @param {Array} nodes - Nodes to check
 * @param {Array} lassoPoints - Points defining the lasso polygon
 * @returns {Array} Node IDs within the lasso
 */
export function findNodesInLasso(nodes, lassoPoints) {
  if (lassoPoints.length < 3) return []

  const selectedIds = []

  nodes.forEach(node => {
    if (isPointInPolygon(node.x, node.y, lassoPoints)) {
      selectedIds.push(node.id)
    }
  })

  return selectedIds
}

/**
 * Check if point is within polygon (ray casting algorithm)
 *
 * @param {number} x - Point x
 * @param {number} y - Point y
 * @param {Array} polygon - Array of {x, y} points
 * @returns {boolean} True if point is inside polygon
 */
function isPointInPolygon(x, y, polygon) {
  let inside = false

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y
    const xj = polygon[j].x, yj = polygon[j].y

    const intersect = ((yi > y) !== (yj > y)) &&
      (x < (xj - xi) * (y - yi) / (yj - yi) + xi)

    if (intersect) inside = !inside
  }

  return inside
}

/**
 * Get interaction mode configuration
 *
 * @param {string} mode - Interaction mode identifier
 * @returns {Object} Mode configuration
 */
export function getInteractionModeConfig(mode) {
  const configs = {
    [INTERACTION_MODES.SELECT]: {
      name: 'Select',
      allowMultiSelect: true,
      maxSelection: 10,
      cursor: 'pointer',
      allowDrag: true,
    },
    [INTERACTION_MODES.PATH]: {
      name: 'Path',
      allowMultiSelect: false,
      maxSelection: 2,
      cursor: 'crosshair',
      allowDrag: false,
    },
    [INTERACTION_MODES.NEIGHBOR]: {
      name: 'Neighbor',
      allowMultiSelect: false,
      maxSelection: 1,
      cursor: 'help',
      allowDrag: false,
    },
    [INTERACTION_MODES.LASSO]: {
      name: 'Lasso',
      allowMultiSelect: false,
      maxSelection: 50,
      cursor: 'cell',
      allowDrag: false,
    },
  }

  return configs[mode] || configs[INTERACTION_MODES.SELECT]
}

/**
 * Validate state for interaction mode
 *
 * @param {string} mode - Interaction mode identifier
 * @param {Object} state - Current interaction state
 * @returns {Object} Validation result {valid, errors}
 */
export function validateInteractionState(mode, state) {
  const errors = []
  const config = getInteractionModeConfig(mode)

  switch (mode) {
    case INTERACTION_MODES.SELECT:
      if (state.selectedNodes?.length > config.maxSelection) {
        errors.push(`Maximum ${config.maxSelection} nodes allowed`)
      }
      break

    case INTERACTION_MODES.PATH:
      if (!state.pathStart && !state.pathEnd) {
        // OK - no nodes selected yet
      } else if (!state.pathStart || !state.pathEnd) {
        errors.push('Select both start and end nodes')
      }
      break

    case INTERACTION_MODES.NEIGHBOR:
      if (!state.selectedNodes || state.selectedNodes.length === 0) {
        errors.push('Select a center node')
      }
      if (state.neighborHops < 1 || state.neighborHops > 5) {
        errors.push('Neighbor hops must be between 1 and 5')
      }
      break

    case INTERACTION_MODES.LASSO:
      // Lasso state is always valid
      break
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}
