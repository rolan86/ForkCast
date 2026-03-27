/**
 * Clustered Layout Algorithm
 *
 * Arranges nodes based on community detection results.
 * Clusters positioned as groups, with force layout within each cluster.
 *
 * @module utils/graph/layouts/clustered
 */

import * as d3 from 'd3'
import { detectCommunities } from '@/utils/graph/clustering/louvain.js'
import { CLUSTERED_LAYOUT_CONFIG } from '@/constants/graph.js'

/**
 * Calculate cluster centroid
 *
 * @param {Array} nodes - Nodes in the cluster
 * @returns {Object} Centroid {x, y}
 */
function calculateClusterCentroid(nodes) {
  if (!nodes.length) {
    return { x: 0, y: 0 }
  }

  const x = nodes.reduce((sum, n) => sum + n.x, 0) / nodes.length
  const y = nodes.reduce((sum, n) => sum + n.y, 0) / nodes.length

  return { x, y }
}

/**
 * Arrange clusters in a circle or grid
 *
 * @param {Array} clusters - Array of cluster objects
 * @param {number} width - Container width
 * @param {number} height - Container height
 * @param {string} arrangement - 'circle' or 'grid'
 * @returns {Map} Cluster ID to center position
 */
function arrangeClusters(clusters, width, height, arrangement = 'circle') {
  const positions = new Map()
  const centerX = width / 2
  const centerY = height / 2

  if (arrangement === 'circle' && clusters.length > 1) {
    // Arrange in a circle
    const radius = Math.min(width, height) / 3
    const angleStep = (2 * Math.PI) / clusters.length

    clusters.forEach((cluster, index) => {
      const angle = index * angleStep
      positions.set(cluster.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      })
    })
  } else {
    // Arrange in a grid
    const cols = Math.ceil(Math.sqrt(clusters.length))
    const cellWidth = width / cols
    const cellHeight = height / Math.ceil(clusters.length / cols)

    clusters.forEach((cluster, index) => {
      const col = index % cols
      const row = Math.floor(index / cols)
      positions.set(cluster.id, {
        x: col * cellWidth + cellWidth / 2,
        y: row * cellHeight + cellHeight / 2,
      })
    })
  }

  return positions
}

/**
 * Run force layout within a cluster
 *
 * @param {Array} clusterNodes - Nodes in the cluster
 * @param {Array} clusterEdges - Edges within the cluster
 * @param {Object} center - Cluster center {x, y}
 * @param {Object} options - Layout options
 * @returns {d3.Simulation} Force simulation
 */
function runClusterForceLayout(clusterNodes, clusterEdges, center, options) {
  const {
    clusterRadius = 100,
    intraClusterDistance = 50,
  } = options

  // Center the cluster
  const offsetX = center.x
  const offsetY = center.y

  const simulation = d3.forceSimulation(clusterNodes)
    .force('link', d3.forceLink(clusterEdges).id(d => d.id).distance(intraClusterDistance))
    .force('charge', d3.forceManyBody().strength(-100))
    .force('center', d3.forceCenter(offsetX, offsetY))
    .force('collide', d3.forceCollide().radius(10))
    .alphaDecay(0.05)
    .velocityDecay(0.5)

  // Run for limited iterations
  simulation.stop()
  for (let i = 0; i < 100; i++) {
    simulation.tick()
  }

  return simulation
}

/**
 * Run clustered layout on graph nodes and edges
 *
 * @param {Array} nodes - Array of node objects with x, y properties
 * @param {Array} edges - Array of edge objects with source, target
 * @param {Object} options - Configuration options
 * @returns {Object} Layout result with positioned nodes and clustering info
 */
export function runClusteredLayout(nodes, edges, options = {}) {
  const {
    width = 800,
    height = 600,
    clusterArrangement = 'circle',
    minClusterSize = CLUSTERED_LAYOUT_CONFIG.minClusterSize,
    maxClusters = CLUSTERED_LAYOUT_CONFIG.maxClusters,
    clusterPadding = CLUSTERED_LAYOUT_CONFIG.clusterPadding,
    interClusterDistance = CLUSTERED_LAYOUT_CONFIG.interClusterDistance,
    runDetection = true,
  } = options

  if (!nodes.length) {
    return { nodes: [], edges, clustering: null }
  }

  // Clone nodes to avoid mutating input
  const layoutNodes = nodes.map(n => ({ ...n, x: n.x || 0, y: n.y || 0 }))

  // Run community detection if requested
  let clusteringResult = null

  if (runDetection && edges.length > 0) {
    clusteringResult = detectCommunities(nodes, edges, {
      minClusterSize,
      maxClusters,
    })
  }

  // If no clusters detected, fall back to force layout
  if (!clusteringResult || clusteringResult.clusterCount === 0) {
    // Simple force layout fallback
    const simulation = d3.forceSimulation(layoutNodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(10))
      .stop()

    for (let i = 0; i < 300; i++) {
      simulation.tick()
    }

    return {
      nodes: layoutNodes,
      edges,
      clustering: {
        clusters: new Map(),
        nodeAssignments: new Map(),
        clusterCount: 0,
      },
    }
  }

  // Arrange clusters
  const clusterArray = Array.from(clusteringResult.clusters.values())
  const clusterPositions = arrangeClusters(clusterArray, width, height, clusterArrangement)

  // Group nodes by cluster
  const clusterNodes = new Map()
  clusteringResult.nodeAssignments.forEach((clusterId, nodeId) => {
    if (!clusterId) return // Skip unassigned nodes

    if (!clusterNodes.has(clusterId)) {
      clusterNodes.set(clusterId, [])
    }
    const node = layoutNodes.find(n => n.id === nodeId)
    if (node) {
      clusterNodes.get(clusterId).push(node)
    }
  })

  // Position nodes within each cluster
  clusterNodes.forEach((nodes, clusterId) => {
    const position = clusterPositions.get(clusterId)
    if (!position) return

    // Find edges within this cluster
    const clusterNodeIds = new Set(nodes.map(n => n.id))
    const clusterEdges = edges.filter(e => {
      const sourceId = e.source.id || e.source
      const targetId = e.target.id || e.target
      return clusterNodeIds.has(sourceId) && clusterNodeIds.has(targetId)
    })

    // Run force layout for this cluster
    if (nodes.length > 1) {
      runClusterForceLayout(nodes, clusterEdges, position, {
        clusterRadius: Math.min(width, height) / (clusterArray.length * 2),
      })
    } else {
      // Single node, place at cluster center
      nodes[0].x = position.x
      nodes[0].y = position.y
    }
  })

  // Position unassigned nodes around the clusters
  const unassignedNodes = layoutNodes.filter(n => !clusteringResult.nodeAssignments.get(n.id))
  if (unassignedNodes.length > 0) {
    const unassignedSimulation = d3.forceSimulation(unassignedNodes)
      .force('charge', d3.forceManyBody().strength(-50))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(10))
      .stop()

    for (let i = 0; i < 100; i++) {
      unassignedSimulation.tick()
    }
  }

  return {
    nodes: layoutNodes,
    edges,
    clustering: clusteringResult,
  }
}

/**
 * Get cluster boundary for visualization
 *
 * @param {string} clusterId - Cluster identifier
 * @param {Array} nodes - All nodes
 * @param {Object} clusteringResult - Result from detectCommunities
 * @returns {Object} Boundary {minX, minY, maxX, maxY, center}
 */
export function getClusterBoundary(clusterId, nodes, clusteringResult) {
  const { nodeAssignments } = clusteringResult

  const clusterNodeIds = new Set()
  nodeAssignments.forEach((cid, nodeId) => {
    if (cid === clusterId) {
      clusterNodeIds.add(nodeId)
    }
  })

  const clusterNodes = nodes.filter(n => clusterNodeIds.has(n.id))

  if (clusterNodes.length === 0) {
    return null
  }

  let minX = Infinity, minY = Infinity
  let maxX = -Infinity, maxY = -Infinity

  clusterNodes.forEach(node => {
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x)
    maxY = Math.max(maxY, node.y)
  })

  const center = {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
  }

  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
    center,
    nodeCount: clusterNodes.length,
  }
}

/**
 * Create super-node for collapsed cluster
 *
 * @param {string} clusterId - Cluster identifier
 * @param {Array} nodes - All nodes
 * @param {Object} clusteringResult - Result from detectCommunities
 * @returns {Object} Super-node object
 */
export function createSuperNode(clusterId, nodes, clusteringResult) {
  const { clusters } = clusteringResult
  const cluster = clusters.get(clusterId)

  if (!cluster) {
    return null
  }

  const clusterNodeIds = new Set(cluster.nodes)
  const clusterNodes = nodes.filter(n => clusterNodeIds.has(n.id))

  const boundary = getClusterBoundary(clusterId, nodes, clusteringResult)

  return {
    id: `super_${clusterId}`,
    type: 'cluster',
    clusterId,
    nodeCount: clusterNodes.length,
    types: cluster.types,
    x: boundary.center.x,
    y: boundary.center.y,
    radius: Math.max(boundary.width, boundary.height) / 2 + 20,
    nodes: cluster.nodes,
  }
}
