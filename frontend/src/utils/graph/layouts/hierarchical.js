/**
 * Hierarchical Layout Algorithm
 *
 * Arranges nodes in a tree hierarchy based on centrality.
 * Root nodes (highest centrality) at top, children below.
 *
 * @module utils/graph/layouts/hierarchical
 */

import * as d3 from 'd3'
import { HIERARCHICAL_LAYOUT_CONFIG } from '@/constants/graph.js'

/**
 * Build tree structure from flat graph data
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {string} rootId - ID of root node
 * @returns {Object} Tree structure with children
 */
function buildTreeStructure(nodes, edges, rootId) {
  const nodeMap = new Map(nodes.map(n => [n.id, { ...n, children: [] }]))
  const visited = new Set()
  const edgeSet = new Set()

  // Build adjacency list from edges
  const adjacency = new Map()
  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target
    edgeSet.add(`${source}-${target}`)
    edgeSet.add(`${target}-${source}`)

    if (!adjacency.has(source)) adjacency.set(source, [])
    if (!adjacency.has(target)) adjacency.set(target, [])
    adjacency.get(source).push(target)
    adjacency.get(target).push(source)
  })

  // Build tree using BFS from root
  function buildTree(nodeId, depth = 0) {
    if (visited.has(nodeId) || depth > 10) return null // Prevent infinite loops
    visited.add(nodeId)

    const node = nodeMap.get(nodeId)
    if (!node) return null

    const neighbors = (adjacency.get(nodeId) || []).filter(id => !visited.has(id))

    // Sort neighbors by connection count (most connected first)
    neighbors.sort((a, b) => {
      const countA = (adjacency.get(a) || []).length
      const countB = (adjacency.get(b) || []).length
      return countB - countA
    })

    node.children = neighbors
      .map(id => buildTree(id, depth + 1))
      .filter(Boolean)

    return node
  }

  return buildTree(rootId)
}

/**
 * Calculate node centrality (degree centrality)
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @returns {Object} Map of node ID to centrality score
 */
function calculateCentrality(nodes, edges) {
  const centrality = {}
  nodes.forEach(n => centrality[n.id] = 0)

  edges.forEach(edge => {
    const source = edge.source.id || edge.source
    const target = edge.target.id || edge.target
    centrality[source] = (centrality[source] || 0) + 1
    centrality[target] = (centrality[target] || 0) + 1
  })

  return centrality
}

/**
 * Find root nodes (highest centrality)
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {number} maxRoots - Maximum number of roots to return
 * @returns {Array} Array of root node IDs
 */
function findRootNodes(nodes, edges, maxRoots = 3) {
  const centrality = calculateCentrality(nodes, edges)

  return nodes
    .map(n => ({ id: n.id, centrality: centrality[n.id] || 0 }))
    .sort((a, b) => b.centrality - a.centrality)
    .slice(0, maxRoots)
    .map(r => r.id)
}

/**
 * Run hierarchical layout on graph nodes and edges
 *
 * @param {Array} nodes - Array of node objects with x, y properties
 * @param {Array} edges - Array of edge objects with source, target
 * @param {Object} options - Configuration options
 * @returns {Object} Layout result with positioned nodes
 */
export function runHierarchicalLayout(nodes, edges, options = {}) {
  const {
    width = 800,
    height = 600,
    nodeWidth = HIERARCHICAL_LAYOUT_CONFIG.nodeWidth,
    nodeHeight = HIERARCHICAL_LAYOUT_CONFIG.nodeHeight,
    levelSpacing = HIERARCHICAL_LAYOUT_CONFIG.levelSpacing,
    siblingSpacing = HIERARCHICAL_LAYOUT_CONFIG.siblingSpacing,
    maxRoots = HIERARCHICAL_LAYOUT_CONFIG.maxRoots,
  } = options

  if (!nodes.length) return { nodes: [], edges }

  // Clone nodes to avoid mutating input
  const layoutNodes = nodes.map(n => ({ ...n, x: 0, y: 0 }))

  // Find root nodes
  const rootIds = findRootNodes(nodes, edges, maxRoots)

  // If no edges, arrange in a simple grid
  if (!edges.length) {
    return arrangeInGrid(layoutNodes, width, height, nodeWidth, nodeHeight)
  }

  // Build tree structure from first root
  const tree = buildTreeStructure(nodes, edges, rootIds[0])

  if (!tree) {
    // Fallback to grid if tree building fails
    return arrangeInGrid(layoutNodes, width, height, nodeWidth, nodeHeight)
  }

  // Create D3 hierarchy
  const root = d3.hierarchy(tree)

  // Calculate tree layout
  const treeLayout = d3.tree()
    .nodeSize([nodeHeight + levelSpacing, nodeWidth + siblingSpacing])
    .separation((a, b) => {
      // Separate nodes by type at same level
      return a.parent === b.parent ? 1.2 : 1.5
    })

  treeLayout(root)

  // Calculate bounds and center the tree
  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity

  root.each(d => {
    minX = Math.min(minX, d.x)
    maxX = Math.max(maxX, d.x)
    minY = Math.min(minY, d.y)
    maxY = Math.max(maxY, d.y)
  })

  const treeWidth = maxX - minX
  const treeHeight = maxY - minY

  const offsetX = (width - treeWidth) / 2 - minX
  const offsetY = (height - treeHeight) / 2 - minY

  // Map positioned nodes back to original nodes
  const positionedNodes = new Map()
  root.each(d => {
    const node = layoutNodes.find(n => n.id === d.data.id)
    if (node) {
      node.x = d.y + offsetX // Swap x/y for horizontal tree
      node.y = d.x + offsetY
      positionedNodes.set(d.data.id, node)
    }
  })

  // Handle unpositioned nodes (disconnected components)
  layoutNodes.forEach(node => {
    if (!positionedNodes.has(node.id)) {
      // Place unpositioned nodes in a grid below the tree
      const unpositionedCount = layoutNodes.filter(n => !positionedNodes.has(n.id)).length
      const index = Array.from(positionedNodes.values()).length
      node.x = (index % 10) * (nodeWidth + siblingSpacing) + 50
      node.y = Math.floor(index / 10) * (nodeHeight + levelSpacing) + treeHeight + offsetY + 50
    }
  })

  return { nodes: layoutNodes, edges }
}

/**
 * Arrange nodes in a simple grid (fallback)
 *
 * @param {Array} nodes - Array of node objects
 * @param {number} width - Container width
 * @param {number} height - Container height
 * @param {number} nodeWidth - Node width
 * @param {number} nodeHeight - Node height
 * @returns {Object} Layout result with positioned nodes
 */
function arrangeInGrid(nodes, width, height, nodeWidth, nodeHeight) {
  const cols = Math.ceil(Math.sqrt(nodes.length))
  const rows = Math.ceil(nodes.length / cols)

  const cellWidth = width / cols
  const cellHeight = height / rows

  nodes.forEach((node, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    node.x = col * cellWidth + cellWidth / 2
    node.y = row * cellHeight + cellHeight / 2
  })

  return { nodes, edges: [] }
}

/**
 * Calculate node levels in hierarchy
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {string} rootId - ID of root node
 * @returns {Object} Map of node ID to level number
 */
export function calculateNodeLevels(nodes, edges, rootId) {
  const levels = {}
  const visited = new Set()

  function setLevel(nodeId, level) {
    if (visited.has(nodeId)) return
    visited.add(nodeId)
    levels[nodeId] = level

    // Find neighbors
    edges.forEach(edge => {
      const source = edge.source.id || edge.source
      const target = edge.target.id || edge.target

      if (source === nodeId && !visited.has(target)) {
        setLevel(target, level + 1)
      } else if (target === nodeId && !visited.has(source)) {
        setLevel(source, level + 1)
      }
    })
  }

  setLevel(rootId, 0)
  return levels
}

/**
 * Get node count per level
 *
 * @param {Object} levels - Map of node ID to level
 * @returns {Object} Map of level to node count
 */
export function getLevelCounts(levels) {
  const counts = {}
  Object.values(levels).forEach(level => {
    counts[level] = (counts[level] || 0) + 1
  })
  return counts
}
