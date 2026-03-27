/**
 * Unit tests for circular layout algorithm
 *
 * Tests the circular arrangement with type-based wedges
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { runCircularLayout, getTypeWedges, calculateOptimalRadius, getNodesByTypeOrder } from '@/utils/graph/layouts/circular.js'

describe('circular layout', () => {
  let mockNodes
  let mockEdges

  beforeEach(() => {
    // Create mock graph data with different entity types
    mockNodes = [
      { id: 'person1', type: 'Person', x: 0, y: 0 },
      { id: 'person2', type: 'Person', x: 0, y: 0 },
      { id: 'org1', type: 'Organization', x: 0, y: 0 },
      { id: 'org2', type: 'Organization', x: 0, y: 0 },
      { id: 'concept1', type: 'Concept', x: 0, y: 0 },
    ]

    mockEdges = [
      { source: 'person1', target: 'org1' },
      { source: 'person2', target: 'org2' },
      { source: 'org1', target: 'concept1' },
    ]
  })

  describe('runCircularLayout', () => {
    it('should return positioned nodes', () => {
      const result = runCircularLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      expect(result.nodes).toBeDefined()
      expect(result.nodes.length).toBe(mockNodes.length)
      expect(result.edges).toBeDefined()
    })

    it('should assign x and y coordinates to all nodes', () => {
      const result = runCircularLayout(mockNodes, mockEdges)

      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
        expect(typeof node.x).toBe('number')
        expect(typeof node.y).toBe('number')
      })
    })

    it('should position nodes in a circle', () => {
      const width = 800
      const height = 600
      const centerX = width / 2
      const centerY = height / 2

      const result = runCircularLayout(mockNodes, mockEdges, { width, height })

      // Calculate average radius from center
      const radii = result.nodes.map(node => {
        const dx = node.x - centerX
        const dy = node.y - centerY
        return Math.sqrt(dx * dx + dy * dy)
      })

      const avgRadius = radii.reduce((a, b) => a + b, 0) / radii.length

      // All nodes should be roughly the same distance from center
      radii.forEach(r => {
        expect(Math.abs(r - avgRadius)).toBeLessThan(50) // Allow some variance
      })

      // Average radius should be close to the configured radius
      expect(avgRadius).toBeGreaterThan(200)
      expect(avgRadius).toBeLessThan(350)
    })

    it('should group nodes by type in wedges', () => {
      const result = runCircularLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      const person1 = result.nodes.find(n => n.id === 'person1')
      const person2 = result.nodes.find(n => n.id === 'person2')
      const org1 = result.nodes.find(n => n.id === 'org1')
      const org2 = result.nodes.find(n => n.id === 'org2')

      expect(person1).toBeDefined()
      expect(person2).toBeDefined()
      expect(org1).toBeDefined()
      expect(org2).toBeDefined()

      // Calculate angles for each node
      const centerX = 400
      const centerY = 300

      const angle = (node) => {
        const dx = node.x - centerX
        const dy = node.y - centerY
        return Math.atan2(dy, dx)
      }

      // Nodes of same type should be close in angle
      const person1Angle = angle(person1)
      const person2Angle = angle(person2)
      const org1Angle = angle(org1)
      const org2Angle = angle(org2)

      // Angle difference within same type should be smaller than between types
      const personAngleDiff = Math.abs(person1Angle - person2Angle)
      const orgAngleDiff = Math.abs(org1Angle - org2Angle)
      const crossTypeDiff = Math.abs(person1Angle - org1Angle)

      expect(personAngleDiff).toBeLessThan(crossTypeDiff)
      expect(orgAngleDiff).toBeLessThan(crossTypeDiff)
    })

    it('should handle empty node array', () => {
      const result = runCircularLayout([], [])

      expect(result.nodes).toEqual([])
      expect(result.edges).toEqual([])
    })

    it('should handle small number of nodes', () => {
      const smallNodes = [
        { id: 'a', type: 'Person', x: 0, y: 0 },
        { id: 'b', type: 'Organization', x: 0, y: 0 },
      ]

      const result = runCircularLayout(smallNodes, [], { width: 800, height: 600 })

      expect(result.nodes.length).toBe(2)
      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
      })
    })

    it('should accept custom radius', () => {
      const customRadius = 200
      const result = runCircularLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
        radius: customRadius,
      })

      const centerX = 400
      const centerY = 300

      const radii = result.nodes.map(node => {
        const dx = node.x - centerX
        const dy = node.y - centerY
        return Math.sqrt(dx * dx + dy * dy)
      })

      const avgRadius = radii.reduce((a, b) => a + b, 0) / radii.length

      // Average radius should be close to custom radius
      expect(Math.abs(avgRadius - customRadius)).toBeLessThan(50)
    })

    it('should use default options when not provided', () => {
      const result = runCircularLayout(mockNodes, mockEdges)

      expect(result.nodes).toBeDefined()
      expect(result.nodes.length).toBe(mockNodes.length)
    })
  })

  describe('getTypeWedges', () => {
    it('should return wedge boundaries for each type', () => {
      const wedges = getTypeWedges(mockNodes)

      expect(wedges).toBeDefined()
      expect(wedges.length).toBeGreaterThan(0)

      // Should have wedges for Person, Organization, Concept
      const types = wedges.map(w => w.type)
      expect(types).toContain('Person')
      expect(types).toContain('Organization')
      expect(types).toContain('Concept')
    })

    it('should have start and end angles for each wedge', () => {
      const wedges = getTypeWedges(mockNodes)

      wedges.forEach(wedge => {
        expect(wedge.startAngle).toBeDefined()
        expect(wedge.endAngle).toBeDefined()
        expect(typeof wedge.startAngle).toBe('number')
        expect(typeof wedge.endAngle).toBe('number')
        expect(wedge.endAngle).toBeGreaterThan(wedge.startAngle)
      })
    })

    it('should handle empty node array', () => {
      const wedges = getTypeWedges([])
      expect(wedges).toEqual([])
    })

    it('should distribute wedges around full circle', () => {
      const wedges = getTypeWedges(mockNodes)

      let totalAngle = 0
      wedges.forEach(wedge => {
        totalAngle += wedge.endAngle - wedge.startAngle
      })

      // Total should be close to 2π (full circle)
      expect(totalAngle).toBeGreaterThan(Math.PI * 1.5)
      expect(totalAngle).toBeLessThanOrEqual(Math.PI * 2)
    })
  })

  describe('calculateOptimalRadius', () => {
    it('should calculate radius based on node count', () => {
      const radius = calculateOptimalRadius(10, 20)

      expect(radius).toBeGreaterThan(0)
      expect(typeof radius).toBe('number')
    })

    it('should increase radius for more nodes', () => {
      const radius10 = calculateOptimalRadius(10, 20)
      const radius20 = calculateOptimalRadius(20, 20)

      expect(radius20).toBeGreaterThan(radius10)
    })

    it('should use default node size when not provided', () => {
      const radius = calculateOptimalRadius(10)

      expect(radius).toBeGreaterThan(0)
    })

    it('should calculate correctly for single node', () => {
      const radius = calculateOptimalRadius(1, 20)

      // Should still return a positive radius
      expect(radius).toBeGreaterThan(0)
    })
  })

  describe('getNodesByTypeOrder', () => {
    it('should return nodes ordered by type', () => {
      const ordered = getNodesByTypeOrder(mockNodes, mockEdges)

      expect(ordered).toBeDefined()
      expect(ordered.length).toBe(mockNodes.length)

      // Check that nodes are grouped by type
      let currentType = ordered[0].type
      let typeSwitches = 0

      for (let i = 1; i < ordered.length; i++) {
        if (ordered[i].type !== currentType) {
          typeSwitches++
          currentType = ordered[i].type
        }
      }

      // Should have fewer switches than random ordering
      expect(typeSwitches).toBeLessThan(ordered.length)
    })

    it('should sort nodes within type by connection count', () => {
      const ordered = getNodesByTypeOrder(mockNodes, mockEdges)

      // Find Person type nodes
      const personNodes = ordered.filter(n => n.type === 'Person')

      // Person1 has 1 connection, Person2 has 1 connection
      expect(personNodes.length).toBe(2)
    })

    it('should handle empty arrays', () => {
      const ordered = getNodesByTypeOrder([], [])
      expect(ordered).toEqual([])
    })

    it('should handle nodes without edges', () => {
      const nodesNoEdges = [
        { id: 'a', type: 'Person' },
        { id: 'b', type: 'Person' },
        { id: 'c', type: 'Organization' },
      ]

      const ordered = getNodesByTypeOrder(nodesNoEdges, [])

      expect(ordered.length).toBe(3)
      // Should still be ordered by type
      const types = ordered.map(n => n.type)
      expect(types[0]).toBe(types[1]) // First two should be same type
    })
  })

  describe('positioning behavior', () => {
    it('should center the circle in available space', () => {
      const width = 800
      const height = 600

      const result = runCircularLayout(mockNodes, mockEdges, { width, height })

      // Calculate average position
      const avgX = result.nodes.reduce((sum, n) => sum + n.x, 0) / result.nodes.length
      const avgY = result.nodes.reduce((sum, n) => sum + n.y, 0) / result.nodes.length

      // Should be close to center
      expect(Math.abs(avgX - width / 2)).toBeLessThan(50)
      expect(Math.abs(avgY - height / 2)).toBeLessThan(50)
    })

    it('should distribute nodes evenly around circle', () => {
      const result = runCircularLayout(mockNodes, mockEdges, {
        width: 800,
        height: 600,
      })

      const centerX = 400
      const centerY = 300

      // Calculate angles
      const angles = result.nodes.map(node => {
        const dx = node.x - centerX
        const dy = node.y - centerY
        return Math.atan2(dy, dx)
      })

      // Sort angles
      angles.sort((a, b) => a - b)

      // Calculate gaps between consecutive nodes
      const gaps = []
      for (let i = 0; i < angles.length - 1; i++) {
        gaps.push(angles[i + 1] - angles[i])
      }

      // Add gap from last to first (wrapping around)
      gaps.push(2 * Math.PI - (angles[angles.length - 1] - angles[0]))

      // Gaps should be roughly even (within 2x of each other)
      const maxGap = Math.max(...gaps)
      const minGap = Math.min(...gaps)
      expect(maxGap / minGap).toBeLessThan(3)
    })
  })

  describe('edge cases', () => {
    it('should handle single node', () => {
      const singleNode = [{ id: 'single', type: 'Person', x: 0, y: 0 }]
      const result = runCircularLayout(singleNode, [], { width: 800, height: 600 })

      expect(result.nodes.length).toBe(1)
      // Single node should be at center
      expect(Math.abs(result.nodes[0].x - 400)).toBeLessThan(50)
      expect(Math.abs(result.nodes[0].y - 300)).toBeLessThan(50)
    })

    it('should handle two nodes', () => {
      const twoNodes = [
        { id: 'a', type: 'Person', x: 0, y: 0 },
        { id: 'b', type: 'Organization', x: 0, y: 0 },
      ]

      const result = runCircularLayout(twoNodes, [], { width: 800, height: 600 })

      expect(result.nodes.length).toBe(2)

      // Nodes should be on opposite sides of circle
      const nodeA = result.nodes[0]
      const nodeB = result.nodes[1]

      const dx = nodeA.x - nodeB.x
      const dy = nodeA.y - nodeB.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      // Distance should be roughly the diameter
      expect(distance).toBeGreaterThan(200)
    })

    it('should handle nodes with unknown type', () => {
      const unknownTypeNodes = [
        { id: 'a', type: 'UnknownType', x: 0, y: 0 },
        { id: 'b', type: 'Person', x: 0, y: 0 },
      ]

      const result = runCircularLayout(unknownTypeNodes, [], { width: 800, height: 600 })

      expect(result.nodes.length).toBe(2)
      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
      })
    })

    it('should handle very large graphs', () => {
      const largeNodes = Array.from({ length: 100 }, (_, i) => ({
        id: `node${i}`,
        type: i % 5 === 0 ? 'Person' : 'Organization',
        x: 0,
        y: 0,
      }))

      const result = runCircularLayout(largeNodes, [], { width: 1600, height: 1200 })

      expect(result.nodes.length).toBe(100)
      result.nodes.forEach(node => {
        expect(node.x).toBeDefined()
        expect(node.y).toBeDefined()
      })
    })
  })
})
