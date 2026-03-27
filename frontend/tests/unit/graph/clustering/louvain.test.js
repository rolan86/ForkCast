/**
 * Unit tests for Louvain community detection
 *
 * Tests the clustering implementation using the louvain library
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  detectCommunities,
  getClusterStats,
  getClusterNodes,
  getInterClusterConnections,
  findMergeCandidates,
} from '@/utils/graph/clustering/louvain.js'

describe('louvain community detection', () => {
  let mockNodes
  let mockEdges

  beforeEach(() => {
    // Create mock graph with clear community structure
    // Community 1: nodes 1-3, interconnected
    // Community 2: nodes 4-6, interconnected
    // Bridge edges between communities
    mockNodes = [
      { id: 'n1', type: 'Person' },
      { id: 'n2', type: 'Person' },
      { id: 'n3', type: 'Person' },
      { id: 'n4', type: 'Organization' },
      { id: 'n5', type: 'Organization' },
      { id: 'n6', type: 'Organization' },
      { id: 'n7', type: 'Concept' }, // Bridge node
    ]

    mockEdges = [
      // Community 1 edges
      { source: 'n1', target: 'n2' },
      { source: 'n2', target: 'n3' },
      { source: 'n3', target: 'n1' },
      // Community 2 edges
      { source: 'n4', target: 'n5' },
      { source: 'n5', target: 'n6' },
      { source: 'n6', target: 'n4' },
      // Bridge edges
      { source: 'n3', target: 'n7' },
      { source: 'n4', target: 'n7' },
    ]
  })

  describe('detectCommunities', () => {
    it('should detect communities in a graph', () => {
      const result = detectCommunities(mockNodes, mockEdges)

      expect(result).toBeDefined()
      expect(result.clusters).toBeInstanceOf(Map)
      expect(result.nodeAssignments).toBeInstanceOf(Map)
      expect(result.clusterCount).toBeGreaterThan(0)
    })

    it('should assign nodes to clusters', () => {
      const result = detectCommunities(mockNodes, mockEdges)

      expect(result.nodeAssignments.size).toBe(mockNodes.length)

      // Each node should have a cluster assignment
      mockNodes.forEach(node => {
        expect(result.nodeAssignments.has(node.id)).toBe(true)
      })
    })

    it('should filter small clusters by default', () => {
      const smallGraphNodes = [
        { id: 'a', type: 'Person' },
        { id: 'b', type: 'Person' },
        { id: 'c', type: 'Person' },
      ]
      const smallGraphEdges = [
        { source: 'a', target: 'b' },
        // Node c is isolated
      ]

      const result = detectCommunities(smallGraphNodes, smallGraphEdges, {
        minClusterSize: 3,
      })

      // Should have no clusters because minimum size is 3
      expect(result.clusterCount).toBe(0)
    })

    it('should respect minClusterSize parameter', () => {
      const result = detectCommunities(mockNodes, mockEdges, {
        minClusterSize: 10,
      })

      // With minClusterSize=10, no clusters should be detected
      expect(result.clusterCount).toBe(0)
    })

    it('should limit number of clusters', () => {
      const result = detectCommunities(mockNodes, mockEdges, {
        maxClusters: 1,
      })

      // Should have at most 1 cluster
      expect(result.clusterCount).toBeLessThanOrEqual(1)
    })

    it('should handle empty graph', () => {
      const result = detectCommunities([], [])

      expect(result.clusterCount).toBe(0)
      expect(result.clusters.size).toBe(0)
      expect(result.nodeAssignments.size).toBe(0)
    })

    it('should handle graph with no edges', () => {
      const result = detectCommunities(mockNodes, [])

      // Each node is its own cluster
      expect(result.clusterCount).toBe(mockNodes.length)
    })

    it('should return cluster metadata', () => {
      const result = detectCommunities(mockNodes, mockEdges)

      result.clusters.forEach((cluster, clusterId) => {
        expect(cluster.id).toBe(clusterId)
        expect(cluster.nodes).toBeInstanceOf(Array)
        expect(cluster.size).toBeGreaterThan(0)
        expect(cluster.types).toBeInstanceOf(Array)
      })
    })
  })

  describe('getClusterStats', () => {
    it('should calculate cluster statistics', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const stats = getClusterStats(clusteringResult)

      expect(stats).toBeDefined()
      expect(stats.totalClusters).toBe(clusteringResult.clusterCount)
      expect(stats.avgClusterSize).toBeGreaterThanOrEqual(0)
      expect(stats.maxClusterSize).toBeGreaterThanOrEqual(0)
      expect(stats.minClusterSize).toBeGreaterThanOrEqual(0)
    })

    it('should return zero stats for empty clustering', () => {
      const emptyResult = {
        clusters: new Map(),
        nodeAssignments: new Map(),
        clusterCount: 0,
      }

      const stats = getClusterStats(emptyResult)

      expect(stats.totalClusters).toBe(0)
      expect(stats.avgClusterSize).toBe(0)
      expect(stats.maxClusterSize).toBe(0)
      expect(stats.minClusterSize).toBe(0)
    })

    it('should provide cluster size distribution', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const stats = getClusterStats(clusteringResult)

      expect(stats.clusterSizeDistribution).toBeInstanceOf(Array)
      expect(stats.clusterSizeDistribution.length).toBe(clusteringResult.clusterCount)
    })
  })

  describe('getClusterNodes', () => {
    it('should return nodes in a cluster', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)

      // Get first cluster
      const firstClusterId = Array.from(clusteringResult.clusters.keys())[0]
      const clusterNodes = getClusterNodes(firstClusterId, clusteringResult, mockNodes)

      expect(clusterNodes).toBeInstanceOf(Array)
      expect(clusterNodes.length).toBeGreaterThan(0)

      // All returned nodes should be in the cluster
      clusterNodes.forEach(node => {
        expect(clusteringResult.nodeAssignments.get(node.id)).toBe(firstClusterId)
      })
    })

    it('should return empty array for unknown cluster', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const clusterNodes = getClusterNodes('unknown_cluster', clusteringResult, mockNodes)

      expect(clusterNodes).toEqual([])
    })
  })

  describe('getInterClusterConnections', () => {
    it('should count connections between clusters', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)

      expect(connections).toBeInstanceOf(Map)
    })

    it('should skip intra-cluster connections', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)

      // No connection should have the same cluster as source and target
      connections.forEach((count, pairKey) => {
        const [cluster1, cluster2] = pairKey.split('-')
        expect(cluster1).not.toBe(cluster2)
      })
    })

    it('should handle graph with single cluster', () => {
      // Create graph where all nodes are strongly connected
      const singleClusterNodes = [
        { id: 'a', type: 'Person' },
        { id: 'b', type: 'Person' },
        { id: 'c', type: 'Person' },
      ]
      const singleClusterEdges = [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
        { source: 'c', target: 'a' },
      ]

      const clusteringResult = detectCommunities(singleClusterNodes, singleClusterEdges)
      const connections = getInterClusterConnections(clusteringResult, singleClusterEdges)

      // Should have no inter-cluster connections
      expect(connections.size).toBe(0)
    })
  })

  describe('findMergeCandidates', () => {
    it('should find clusters with strong connections', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)
      const candidates = findMergeCandidates(connections, 1)

      expect(candidates).toBeInstanceOf(Array)
    })

    it('should return empty array when no connections above threshold', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)
      const candidates = findMergeCandidates(connections, 1000)

      expect(candidates).toEqual([])
    })

    it('should sort candidates by connection count', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)
      const candidates = findMergeCandidates(connections, 1)

      // Verify descending order by connection count
      for (let i = 1; i < candidates.length; i++) {
        expect(candidates[i - 1].connectionCount).toBeGreaterThanOrEqual(candidates[i].connectionCount)
      }
    })

    it('should include cluster pair and connection count', () => {
      const clusteringResult = detectCommunities(mockNodes, mockEdges)
      const connections = getInterClusterConnections(clusteringResult, mockEdges)
      const candidates = findMergeCandidates(connections, 1)

      candidates.forEach(candidate => {
        expect(candidate.cluster1).toBeDefined()
        expect(candidate.cluster2).toBeDefined()
        expect(candidate.connectionCount).toBeGreaterThan(0)
      })
    })
  })

  describe('error handling', () => {
    it('should handle invalid edge references gracefully', () => {
      const invalidEdges = [
        { source: 'n1', target: 'unknown_node' }, // Invalid target
      ]

      const result = detectCommunities(mockNodes, invalidEdges)

      // Should not throw, should return result
      expect(result).toBeDefined()
      expect(result.clusterCount).toBeGreaterThanOrEqual(0)
    })

    it('should handle edges with node objects instead of IDs', () => {
      const edgesWithObjects = [
        { source: { id: 'n1' }, target: { id: 'n2' } },
        { source: { id: 'n2' }, target: { id: 'n3' } },
      ]

      const result = detectCommunities(mockNodes, edgesWithObjects)

      expect(result).toBeDefined()
    })
  })

  describe('edge cases', () => {
    it('should handle single node', () => {
      const singleNode = [{ id: 'single', type: 'Person' }]
      const result = detectCommunities(singleNode, [])

      expect(result.clusterCount).toBe(1)
      expect(result.nodeAssignments.get('single')).toBeTruthy()
    })

    it('should handle two connected nodes', () => {
      const twoNodes = [
        { id: 'a', type: 'Person' },
        { id: 'b', type: 'Organization' },
      ]
      const twoEdges = [{ source: 'a', target: 'b' }]

      const result = detectCommunities(twoNodes, twoEdges)

      // With minClusterSize=3 default, no cluster should be detected
      expect(result.clusterCount).toBe(0)
    })

    it('should handle disconnected components', () => {
      const disconnectedNodes = [
        { id: 'a', type: 'Person' },
        { id: 'b', type: 'Person' },
        { id: 'c', type: 'Organization' },
        { id: 'd', type: 'Organization' },
      ]
      const disconnectedEdges = [
        { source: 'a', target: 'b' }, // Component 1
        { source: 'c', target: 'd' }, // Component 2
      ]

      const result = detectCommunities(disconnectedNodes, disconnectedEdges)

      // Should detect at least one cluster
      expect(result.clusterCount).toBeGreaterThan(0)
    })
  })
})
