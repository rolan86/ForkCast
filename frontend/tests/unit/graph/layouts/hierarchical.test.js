/**
 * Unit tests for hierarchical layout algorithm
 *
 * Tests the tree-based hierarchical layout implementation
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { runHierarchicalLayout, calculateNodeLevels, getLevelCounts } from '@/utils/graph/layouts/hierarchical.js'

describe('hierarchical layout', () => {
  let mockNodes
  let mockEdges

  beforeEach(() => {
    // Create mock graph data
    mockNodes = [
      { id: 'root', type: 'Person', x: 0, y: 0 },
      { id: 'child1', type: 'Organization', x: 0, y: 0 },
      { id: 'child2', type: 'Organization', x: 0, y: 0 },
      { id: 'grandchild1', type: 'Concept', x: 0, y: 0 },
      { id: 'grandchild2', type: 'Concept', x: 0, y: 0 },
    ]

    mockEdges = [
      { source: 'root', target: 'child1' },
      { source: 'root', target: 'child2' },
      { source: 'child1', target: 'grandchild1' },
      { source: 'child2', target: 'grandchild2' },
    ]
  })

  describe('runHierarchicalLayout', () => {
    it('should return positioned nodes', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      expect(result.nodes).toBeDefined()
      expect(result.nodes.length).toBe(mockNodes.length)
      expect(result.edges).toBeDefined()
    })

    it('should assign x and y coordinates to all nodes', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges)

      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
        expect(typeof node.x).toBe('number')
        expect(typeof node.y).toBe('number')
      })
    })

    it('should position root node near top center', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      const root = result.nodes.find(n => n.id === 'root')
      expect(root).toBeDefined()
      // Root should be near the top and horizontally centered
      expect(root.y).toBeLessThan(200) // Top portion
      expect(root.x).toBeGreaterThan(300) // Near center
      expect(root.x).toBeLessThan(500)
    })

    it('should position children below root', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      const root = result.nodes.find(n => n.id === 'root')
      const child1 = result.nodes.find(n => n.id === 'child1')
      const child2 = result.nodes.find(n => n.id === 'child2')

      expect(root).toBeDefined()
      expect(child1).toBeDefined()
      expect(child2).toBeDefined()

      // Children should be below root
      expect(child1.y).toBeGreaterThan(root.y)
      expect(child2.y).toBeGreaterThan(root.y)
    })

    it('should handle empty node array', () => {
      const result = runHierarchicalLayout([], [])

      expect(result.nodes).toEqual([])
      expect(result.edges).toEqual([])
    })

    it('should handle disconnected nodes', () => {
      const disconnectedNodes = [
        { id: 'node1', type: 'Person', x: 0, y: 0 },
        { id: 'node2', type: 'Organization', x: 0, y: 0 },
      ]

      const result = runHierarchicalLayout(disconnectedNodes, [], {
        width: 800,
        height: 600,
      })

      expect(result.nodes.length).toBe(2)
      result.nodes.forEach(node => {
        expect(node.x).toBeGreaterThanOrEqual(0)
        expect(node.y).toBeGreaterThanOrEqual(0)
      })
    })

    it('should handle nodes without edges', () => {
      const result = runHierarchicalLayout(mockNodes, [], {
        width: 800,
        height: 600,
      })

      expect(result.nodes.length).toBe(mockNodes.length)
      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
      })
    })

    it('should accept custom configuration options', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges, {
        width: 1000,
        height: 800,
        nodeWidth: 150,
        nodeHeight: 60,
        levelSpacing: 100,
        siblingSpacing: 40,
      })

      expect(result.nodes).toBeDefined()
      expect(result.nodes.length).toBe(mockNodes.length)
    })

    it('should use default options when not provided', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges)

      expect(result.nodes).toBeDefined()
      expect(result.nodes.length).toBe(mockNodes.length)
    })
  })

  describe('calculateNodeLevels', () => {
    it('should calculate levels from root', () => {
      const levels = calculateNodeLevels(mockNodes, mockEdges, 'root')

      expect(levels['root']).toBe(0)
      expect(levels['child1']).toBe(1)
      expect(levels['child2']).toBe(1)
      expect(levels['grandchild1']).toBe(2)
      expect(levels['grandchild2']).toBe(2)
    })

    it('should handle disconnected node', () => {
      const levels = calculateNodeLevels(mockNodes, mockEdges, 'root')

      // All connected nodes should have levels
      expect(levels['root']).toBeDefined()
      expect(levels['child1']).toBeDefined()
    })

    it('should start from specified root', () => {
      const levels = calculateNodeLevels(mockNodes, mockEdges, 'child1')

      expect(levels['child1']).toBe(0)
      expect(levels['root']).toBe(1)
      expect(levels['grandchild1']).toBe(1)
    })
  })

  describe('getLevelCounts', () => {
    it('should count nodes per level', () => {
      const levels = {
        'root': 0,
        'child1': 1,
        'child2': 1,
        'grandchild1': 2,
        'grandchild2': 2,
      }

      const counts = getLevelCounts(levels)

      expect(counts[0]).toBe(1) // 1 node at level 0
      expect(counts[1]).toBe(2) // 2 nodes at level 1
      expect(counts[2]).toBe(2) // 2 nodes at level 2
    })

    it('should handle empty levels object', () => {
      const counts = getLevelCounts({})
      expect(Object.keys(counts).length).toBe(0)
    })

    it('should handle single level', () => {
      const levels = {
        'node1': 0,
        'node2': 0,
        'node3': 0,
      }

      const counts = getLevelCounts(levels)
      expect(counts[0]).toBe(3)
    })
  })

  describe('tree structure building', () => {
    it('should build tree from root', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges)

      // Verify all nodes are positioned
      const allNodesPositioned = result.nodes.every(n =>
        n.x !== undefined && n.y !== undefined
      )
      expect(allNodesPositioned).toBe(true)
    })

    it('should handle circular graph without infinite loop', () => {
      const circularNodes = [
        { id: 'a', type: 'Person', x: 0, y: 0 },
        { id: 'b', type: 'Person', x: 0, y: 0 },
        { id: 'c', type: 'Person', x: 0, y: 0 },
      ]

      const circularEdges = [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
        { source: 'c', target: 'a' },
      ]

      const result = runHierarchicalLayout(circularNodes, circularEdges)
      expect(result.nodes.length).toBe(3)
    })
  })

  describe('positioning behavior', () => {
    it('should spread nodes horizontally within levels', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges)

      const child1 = result.nodes.find(n => n.id === 'child1')
      const child2 = result.nodes.find(n => n.id === 'child2')

      expect(child1).toBeDefined()
      expect(child2).toBeDefined()

      // Siblings should have different x positions
      expect(child1.x).not.toBe(child2.x)
    })

    it('should position children at different vertical levels', () => {
      const result = runHierarchicalLayout(mockNodes, mockEdges)

      const root = result.nodes.find(n => n.id === 'root')
      const child1 = result.nodes.find(n => n.id === 'child1')
      const grandchild1 = result.nodes.find(n => n.id === 'grandchild1')

      expect(root.y).toBeLessThan(child1.y)
      expect(child1.y).toBeLessThan(grandchild1.y)
    })

    it('should center tree in available space', () => {
      const width = 800
      const height = 600

      const result = runHierarchicalLayout(mockNodes, mockEdges, {
        width,
        height,
      })

      // Find bounds
      let minX = Infinity, maxX = -Infinity
      let minY = Infinity, maxY = -Infinity

      result.nodes.forEach(n => {
        minX = Math.min(minX, n.x)
        maxX = Math.max(maxX, n.x)
        minY = Math.min(minY, n.y)
        maxY = Math.max(maxY, n.y)
      })

      // Tree should be roughly centered
      const centerX = (minX + maxX) / 2
      const centerY = (minY + maxY) / 2

      expect(centerX).toBeGreaterThan(width * 0.3)
      expect(centerX).toBeLessThan(width * 0.7)
      expect(centerY).toBeGreaterThan(height * 0.2)
      expect(centerY).toBeLessThan(height * 0.8)
    })
  })

  describe('edge cases', () => {
    it('should handle single node', () => {
      const singleNode = [{ id: 'single', type: 'Person', x: 0, y: 0 }]
      const result = runHierarchicalLayout(singleNode, [], { width: 800, height: 600 })

      expect(result.nodes.length).toBe(1)
      expect(result.nodes[0].x).toBe(400) // Center
      expect(result.nodes[0].y).toBe(300) // Center
    })

    it('should handle two connected nodes', () => {
      const twoNodes = [
        { id: 'a', type: 'Person', x: 0, y: 0 },
        { id: 'b', type: 'Organization', x: 0, y: 0 },
      ]
      const twoEdges = [{ source: 'a', target: 'b' }]

      const result = runHierarchicalLayout(twoNodes, twoEdges, { width: 800, height: 600 })

      expect(result.nodes.length).toBe(2)

      const nodeA = result.nodes.find(n => n.id === 'a')
      const nodeB = result.nodes.find(n => n.id === 'b')

      expect(nodeA).toBeDefined()
      expect(nodeB).toBeDefined()

      // Nodes should be at different y positions (one above the other)
      expect(nodeA.y).not.toBe(nodeB.y)
    })

    it('should handle very large graphs without error', () => {
      const largeNodes = Array.from({ length: 100 }, (_, i) => ({
        id: `node${i}`,
        type: 'Person',
        x: 0,
        y: 0,
      }))

      const largeEdges = []
      for (let i = 0; i < 99; i++) {
        largeEdges.push({ source: `node${i}`, target: `node${i + 1}` })
      }

      const result = runHierarchicalLayout(largeNodes, largeEdges, {
        width: 1600,
        height: 1200,
      })

      expect(result.nodes.length).toBe(100)
    })
  })
})
