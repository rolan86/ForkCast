/**
 * Unit tests for interaction modes
 *
 * Tests the path finding, neighbor detection, and interaction mode utilities
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  findShortestPath,
  findNeighbors,
  findCommonConnections,
  extractSubgraph,
  handleSelectClick,
  findNodesInLasso,
  getInteractionModeConfig,
  validateInteractionState,
} from '@/utils/graph/interactions/modes.js'
import { INTERACTION_MODES } from '@/constants/graph.js'

describe('interaction modes', () => {
  let mockNodes
  let mockEdges

  beforeEach(() => {
    mockNodes = [
      { id: 'a', x: 100, y: 100 },
      { id: 'b', x: 200, y: 150 },
      { id: 'c', x: 150, y: 200 },
      { id: 'd', x: 250, y: 200 },
      { id: 'e', x: 300, y: 100 },
    ]

    mockEdges = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'c' },
      { source: 'c', target: 'd' },
      { source: 'd', target: 'e' },
      { source: 'a', target: 'c' }, // Shortcut
    ]
  })

  describe('findShortestPath', () => {
    it('should find path between connected nodes', () => {
      const path = findShortestPath('a', 'd', mockNodes, mockEdges)

      expect(path).toBeDefined()
      expect(path.length).toBeGreaterThan(0)
      expect(path[0]).toBe('a')
      expect(path[path.length - 1]).toBe('d')
    })

    it('should return single node when start equals end', () => {
      const path = findShortestPath('a', 'a', mockNodes, mockEdges)

      expect(path).toEqual(['a'])
    })

    it('should find shortest path using shortcuts', () => {
      // Path a -> c can be direct (via shortcut) or through b
      const path = findShortestPath('a', 'c', mockNodes, mockEdges)

      expect(path).toEqual(['a', 'c']) // Should take direct shortcut
    })

    it('should return empty array when no path exists', () => {
      const isolatedNodes = [
        { id: 'x', x: 0, y: 0 },
        { id: 'y', x: 100, y: 100 },
      ]
      const isolatedEdges = [] // No edges

      const path = findShortestPath('x', 'y', isolatedNodes, isolatedEdges)

      expect(path).toEqual([])
    })

    it('should handle edges with node objects', () => {
      const edgesWithObjects = [
        { source: { id: 'a' }, target: { id: 'b' } },
        { source: { id: 'b' }, target: { id: 'c' } },
      ]

      const path = findShortestPath('a', 'c', mockNodes, edgesWithObjects)

      expect(path).toEqual(['a', 'b', 'c'])
    })
  })

  describe('findNeighbors', () => {
    it('should find direct neighbors (1 hop)', () => {
      const neighbors = findNeighbors('a', 1, mockNodes, mockEdges)

      expect(neighbors).toBeInstanceOf(Set)
      expect(neighbors.has('a')).toBe(true) // Include self
      expect(neighbors.has('b')).toBe(true)
      expect(neighbors.has('c')).toBe(true)
      expect(neighbors.has('d')).toBe(false) // Not in 1-hop
    })

    it('should find 2-hop neighbors', () => {
      const neighbors = findNeighbors('a', 2, mockNodes, mockEdges)

      expect(neighbors.has('a')).toBe(true)
      expect(neighbors.has('b')).toBe(true)
      expect(neighbors.has('c')).toBe(true)
      expect(neighbors.has('d')).toBe(true) // 2 hops from a
      expect(neighbors.has('e')).toBe(false) // More than 2 hops
    })

    it('should return only self when hops is 0', () => {
      const neighbors = findNeighbors('a', 0, mockNodes, mockEdges)

      expect(neighbors.size).toBe(1)
      expect(neighbors.has('a')).toBe(true)
    })

    it('should handle isolated node', () => {
      const isolatedNodes = [{ id: 'x', x: 0, y: 0 }]
      const neighbors = findNeighbors('x', 2, isolatedNodes, [])

      expect(neighbors.size).toBe(1)
      expect(neighbors.has('x')).toBe(true)
    })
  })

  describe('findCommonConnections', () => {
    it('should find common connections between two nodes', () => {
      const common = findCommonConnections('a', 'c', mockEdges)

      expect(common).toContain('b') // Both connected to b
    })

    it('should return empty array when no common connections', () => {
      const common = findCommonConnections('a', 'e', mockEdges)

      expect(common).toEqual([])
    })

    it('should handle edges with node objects', () => {
      const edgesWithObjects = [
        { source: { id: 'a' }, target: { id: 'x' } },
        { source: { id: 'b' }, target: { id: 'x' } },
        { source: { id: 'c' }, target: { id: 'x' } },
      ]

      const common = findCommonConnections('a', 'b', edgesWithObjects)

      expect(common).toContain('x')
    })
  })

  describe('extractSubgraph', () => {
    it('should extract subgraph around a node', () => {
      const subgraph = extractSubgraph('c', 1, mockNodes, mockEdges)

      expect(subgraph.nodes).toBeDefined()
      expect(subgraph.edges).toBeDefined()
      expect(subgraph.centerNodeId).toBe('c')

      // Should include nodes within 1 hop
      const nodeIds = new Set(subgraph.nodes.map(n => n.id))
      expect(nodeIds.has('a')).toBe(true)
      expect(nodeIds.has('b')).toBe(true)
      expect(nodeIds.has('c')).toBe(true)
      expect(nodeIds.has('d')).toBe(true)
    })

    it('should only include edges between subgraph nodes', () => {
      const subgraph = extractSubgraph('a', 1, mockNodes, mockEdges)

      subgraph.edges.forEach(edge => {
        const source = edge.source.id || edge.source
        const target = edge.target.id || edge.target
        const nodeIds = new Set(subgraph.nodes.map(n => n.id))
        expect(nodeIds.has(source)).toBe(true)
        expect(nodeIds.has(target)).toBe(true)
      })
    })

    it('should return empty subgraph for unknown node', () => {
      const subgraph = extractSubgraph('unknown', 1, mockNodes, mockEdges)

      expect(subgraph.nodes).toEqual([])
      expect(subgraph.edges).toEqual([])
    })
  })

  describe('handleSelectClick', () => {
    it('should replace selection in single-select mode', () => {
      const currentSelection = ['node1', 'node2']
      const newSelection = handleSelectClick('node3', currentSelection, false)

      expect(newSelection).toEqual(['node3'])
    })

    it('should add node in multi-select mode', () => {
      const currentSelection = ['node1']
      const newSelection = handleSelectClick('node2', currentSelection, true)

      expect(newSelection).toEqual(['node1', 'node2'])
    })

    it('should remove node if already selected in multi-select', () => {
      const currentSelection = ['node1', 'node2']
      const newSelection = handleSelectClick('node1', currentSelection, true)

      expect(newSelection).toEqual(['node2'])
    })

    it('should respect max selection limit', () => {
      const currentSelection = ['node1', 'node2', 'node3'] // Already at limit
      const newSelection = handleSelectClick('node4', currentSelection, true, 3)

      expect(newSelection).toEqual(['node1', 'node2', 'node3'])
    })
  })

  describe('findNodesInLasso', () => {
    it('should find nodes inside lasso polygon', () => {
      const nodes = [
        { id: 'n1', x: 100, y: 100 },
        { id: 'n2', x: 200, y: 100 },
        { id: 'n3', x: 150, y: 200 },
      ]

      const lassoPoints = [
        { x: 50, y: 50 },
        { x: 250, y: 50 },
        { x: 250, y: 250 },
        { x: 50, y: 250 },
      ]

      const selected = findNodesInLasso(nodes, lassoPoints)

      expect(selected.length).toBe(3)
      expect(selected).toContain('n1')
      expect(selected).toContain('n2')
      expect(selected).toContain('n3')
    })

    it('should not select nodes outside lasso', () => {
      const nodes = [
        { id: 'inside', x: 100, y: 100 },
        { id: 'outside', x: 500, y: 500 },
      ]

      const lassoPoints = [
        { x: 50, y: 50 },
        { x: 150, y: 50 },
        { x: 150, y: 150 },
        { x: 50, y: 150 },
      ]

      const selected = findNodesInLasso(nodes, lassoPoints)

      expect(selected).toEqual(['inside'])
    })

    it('should return empty array with insufficient points', () => {
      const nodes = [{ id: 'n1', x: 100, y: 100 }]
      const lassoPoints = [{ x: 50, y: 50 }]

      const selected = findNodesInLasso(nodes, lassoPoints)

      expect(selected).toEqual([])
    })
  })

  describe('getInteractionModeConfig', () => {
    it('should return config for SELECT mode', () => {
      const config = getInteractionModeConfig(INTERACTION_MODES.SELECT)

      expect(config.name).toBe('Select')
      expect(config.allowMultiSelect).toBe(true)
      expect(config.maxSelection).toBe(10)
      expect(config.cursor).toBe('pointer')
    })

    it('should return config for PATH mode', () => {
      const config = getInteractionModeConfig(INTERACTION_MODES.PATH)

      expect(config.name).toBe('Path')
      expect(config.allowMultiSelect).toBe(false)
      expect(config.maxSelection).toBe(2)
    })

    it('should return config for NEIGHBOR mode', () => {
      const config = getInteractionModeConfig(INTERACTION_MODES.NEIGHBOR)

      expect(config.name).toBe('Neighbor')
      expect(config.allowDrag).toBe(false)
    })

    it('should return config for LASSO mode', () => {
      const config = getInteractionModeConfig(INTERACTION_MODES.LASSO)

      expect(config.name).toBe('Lasso')
      expect(config.maxSelection).toBe(50)
      expect(config.cursor).toBe('cell')
    })
  })

  describe('validateInteractionState', () => {
    it('should validate SELECT mode state', () => {
      const state = { selectedNodes: ['n1', 'n2'] }
      const result = validateInteractionState(INTERACTION_MODES.SELECT, state)

      expect(result.valid).toBe(true)
      expect(result.errors).toEqual([])
    })

    it('should reject SELECT mode with too many nodes', () => {
      const state = { selectedNodes: Array(15).fill('node') }
      const result = validateInteractionState(INTERACTION_MODES.SELECT, state)

      expect(result.valid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('should validate PATH mode with both nodes', () => {
      const state = { pathStart: 'n1', pathEnd: 'n2' }
      const result = validateInteractionState(INTERACTION_MODES.PATH, state)

      expect(result.valid).toBe(true)
    })

    it('should reject PATH mode with only start node', () => {
      const state = { pathStart: 'n1', pathEnd: null }
      const result = validateInteractionState(INTERACTION_MODES.PATH, state)

      expect(result.valid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('should validate NEIGHBOR mode with valid hops', () => {
      const state = { selectedNodes: ['n1'], neighborHops: 2 }
      const result = validateInteractionState(INTERACTION_MODES.NEIGHBOR, state)

      expect(result.valid).toBe(true)
    })

    it('should reject NEIGHBOR mode with invalid hops', () => {
      const state = { selectedNodes: ['n1'], neighborHops: 10 }
      const result = validateInteractionState(INTERACTION_MODES.NEIGHBOR, state)

      expect(result.valid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('should always accept LASSO mode state', () => {
      const result = validateInteractionState(INTERACTION_MODES.LASSO, {})

      expect(result.valid).toBe(true)
    })
  })
})
