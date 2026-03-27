/**
 * Louvain Community Detection
 *
 * Implements community detection using the Louvain algorithm.
 * Groups nodes into clusters based on connection density.
 *
 * @module utils/graph/clustering/louvain
 */

import louvain from 'louvain'

/**
 * Convert graph nodes and edges to Louvain format
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @returns {Object} Graph in Louvain format {nodes, edges}
 */
function convertToLouvainFormat(nodes, edges) {
  // Create node ID mapping
  const nodeIdMap = new Map()
  nodes.forEach((node, index) => {
    nodeIdMap.set(node.id, index)
  })

  // Convert edges to Louvain format (index pairs)
  const louvainEdges = edges.map(edge => {
    const sourceId = edge.source.id || edge.source
    const targetId = edge.target.id || edge.target

    const sourceIndex = nodeIdMap.get(sourceId)
    const targetIndex = nodeIdMap.get(targetId)

    if (sourceIndex === undefined || targetIndex === undefined) {
      console.warn(`Edge references unknown node: ${sourceId} -> ${targetId}`)
      return null
    }

    return [sourceIndex, targetIndex]
  }).filter(Boolean)

  return {
    nodes: nodes.map(n => ({ id: n.id, ...n })),
    edges: louvainEdges,
  }
}

/**
 * Run Louvain community detection
 *
 * @param {Array} nodes - Array of node objects
 * @param {Array} edges - Array of edge objects
 * @param {Object} options - Configuration options
 * @returns {Object} Clustering result with node assignments
 */
export function detectCommunities(nodes, edges, options = {}) {
  const {
    minClusterSize = 3,
    maxClusters = 20,
    resolution = 1.0,
  } = options

  if (!nodes.length || !edges.length) {
    return {
      clusters: new Map(),
      nodeAssignments: new Map(),
      clusterCount: 0,
    }
  }

  try {
    // Convert to Louvain format
    const { edges: louvainEdges } = convertToLouvainFormat(nodes, edges)

    if (louvainEdges.length === 0) {
      // No edges, each node is its own cluster
      const assignments = new Map()
      nodes.forEach((node, index) => {
        assignments.set(node.id, index)
      })

      return {
        clusters: new Map(),
        nodeAssignments: assignments,
        clusterCount: nodes.length,
      }
    }

    // Run Louvain algorithm
    const communityIds = louvain.j(louvainEdges, resolution)

    // Create node ID to cluster ID mapping
    const nodeAssignments = new Map()
    const clusterMembers = new Map()

    nodes.forEach((node, index) => {
      const clusterId = communityIds[index]
      nodeAssignments.set(node.id, clusterId)

      if (!clusterMembers.has(clusterId)) {
        clusterMembers.set(clusterId, [])
      }
      clusterMembers.get(clusterId).push(node)
    })

    // Filter small clusters
    const filteredAssignments = new Map()
    const filteredClusters = new Map()
    let nextClusterId = 0

    clusterMembers.forEach((members, originalClusterId) => {
      if (members.length >= minClusterSize) {
        // Create new cluster
        const newClusterId = `cluster_${nextClusterId++}`
        filteredClusters.set(newClusterId, {
          id: newClusterId,
          nodes: members.map(n => n.id),
          size: members.length,
          types: [...new Set(members.map(n => n.type))],
        })

        // Update assignments
        members.forEach(node => {
          filteredAssignments.set(node.id, newClusterId)
        })
      } else {
        // Nodes in small clusters are unassigned
        members.forEach(node => {
          filteredAssignments.set(node.id, null)
        })
      }
    })

    // Limit number of clusters
    if (filteredClusters.size > maxClusters) {
      // Keep only largest clusters
      const sortedClusters = Array.from(filteredClusters.entries())
        .sort((a, b) => b[1].size - a[1].size)
        .slice(0, maxClusters)

      const limitedClusters = new Map(sortedClusters)
      const validClusterIds = new Set(sortedClusters.map(([id]) => id))

      // Update assignments to remove nodes from excluded clusters
      filteredAssignments.forEach((clusterId, nodeId) => {
        if (clusterId && !validClusterIds.has(clusterId)) {
          filteredAssignments.set(nodeId, null)
        }
      })

      return {
        clusters: limitedClusters,
        nodeAssignments: filteredAssignments,
        clusterCount: limitedClusters.size,
      }
    }

    return {
      clusters: filteredClusters,
      nodeAssignments: filteredAssignments,
      clusterCount: filteredClusters.size,
    }
  } catch (error) {
    console.error('Louvain detection failed:', error)
    // Return empty clustering on error
    return {
      clusters: new Map(),
      nodeAssignments: new Map(),
      clusterCount: 0,
      error: error.message,
    }
  }
}

/**
 * Get cluster statistics
 *
 * @param {Object} clusteringResult - Result from detectCommunities
 * @returns {Object} Statistics about the clustering
 */
export function getClusterStats(clusteringResult) {
  const { clusters } = clusteringResult

  if (!clusters || clusters.size === 0) {
    return {
      totalClusters: 0,
      avgClusterSize: 0,
      maxClusterSize: 0,
      minClusterSize: 0,
      clusterSizeDistribution: [],
    }
  }

  const sizes = Array.from(clusters.values()).map(c => c.size)

  return {
    totalClusters: clusters.size,
    avgClusterSize: sizes.reduce((a, b) => a + b, 0) / sizes.length,
    maxClusterSize: Math.max(...sizes),
    minClusterSize: Math.min(...sizes),
    clusterSizeDistribution: sizes.sort((a, b) => b - a),
  }
}

/**
 * Get nodes for a specific cluster
 *
 * @param {string} clusterId - Cluster identifier
 * @param {Object} clusteringResult - Result from detectCommunities
 * @param {Array} nodes - Original node array
 * @returns {Array} Nodes in the cluster
 */
export function getClusterNodes(clusterId, clusteringResult, nodes) {
  const { clusters } = clusteringResult

  if (!clusters || !clusters.has(clusterId)) {
    return []
  }

  const cluster = clusters.get(clusterId)
  const clusterNodeIds = new Set(cluster.nodes)

  return nodes.filter(n => clusterNodeIds.has(n.id))
}

/**
 * Get connections between clusters
 *
 * @param {Object} clusteringResult - Result from detectCommunities
 * @param {Array} edges - Original edge array
 * @returns {Map} Map of cluster pair to connection count
 */
export function getInterClusterConnections(clusteringResult, edges) {
  const { nodeAssignments } = clusteringResult
  const connections = new Map()

  edges.forEach(edge => {
    const sourceId = edge.source.id || edge.source
    const targetId = edge.target.id || edge.target

    const sourceCluster = nodeAssignments.get(sourceId)
    const targetCluster = nodeAssignments.get(targetId)

    // Skip if either node is not in a cluster
    if (!sourceCluster || !targetCluster) {
      return
    }

    // Skip intra-cluster connections
    if (sourceCluster === targetCluster) {
      return
    }

    // Create cluster pair key
    const pairKey = [sourceCluster, targetCluster].sort().join('-')
    connections.set(pairKey, (connections.get(pairKey) || 0) + 1)
  })

  return connections
}

/**
 * Find clusters that should be merged
 *
 * @param {Map} interClusterConnections - Result from getInterClusterConnections
 * @param {number} threshold - Minimum connection count to consider merging
 * @returns {Array} Array of cluster pairs that should merge
 */
export function findMergeCandidates(interClusterConnections, threshold = 5) {
  const candidates = []

  interClusterConnections.forEach((count, pairKey) => {
    if (count >= threshold) {
      const [cluster1, cluster2] = pairKey.split('-')
      candidates.push({ cluster1, cluster2, connectionCount: count })
    }
  })

  return candidates.sort((a, b) => b.connectionCount - a.connectionCount)
}
