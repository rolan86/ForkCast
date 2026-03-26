/**
 * Unit tests for useGraphState composable
 *
 * Tests the reactive state management for graph UI
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useGraphState } from '@/composables/useGraphState.js'
import { LAYOUT_TYPES, VISUAL_MODES, RENDER_MODES, INTERACTION_MODES } from '@/constants/graph.js'

describe('useGraphState', () => {
  let composable

  beforeEach(() => {
    // Clear localStorage before each test
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(() => {}),
      removeItem: vi.fn(() => {}),
    })
    composable = useGraphState()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('initialization', () => {
    it('should return reactive state object', () => {
      expect(composable.graphState).toBeDefined()
      expect(composable.graphState.layout).toBe(LAYOUT_TYPES.FORCE)
      expect(composable.graphState.visualMode).toBe(VISUAL_MODES.TWO_POINT_FIVE_D)
      expect(composable.graphState.renderMode).toBe(RENDER_MODES.HYBRID)
    })

    it('should initialize with default clustering state', () => {
      expect(composable.graphState.clustering.enabled).toBe(false)
      expect(composable.graphState.clustering.autoDetect).toBe(true)
      expect(composable.graphState.clustering.expandedClusters).toBeInstanceOf(Set)
    })

    it('should initialize with default selection state', () => {
      expect(composable.graphState.selection.nodes).toEqual([])
      expect(composable.graphState.selection.mode).toBe(INTERACTION_MODES.SELECT)
      expect(composable.graphState.selection.pathStart).toBeNull()
      expect(composable.graphState.selection.pathEnd).toBeNull()
      expect(composable.graphState.selection.neighborHops).toBe(1)
    })

    it('should initialize with default view state', () => {
      expect(composable.graphState.view.zoom).toBe(1)
      expect(composable.graphState.view.pan).toEqual({ x: 0, y: 0 })
      expect(composable.graphState.view.viewport).toEqual({ x: 0, y: 0, w: 0, h: 0 })
    })

    it('should initialize with performance mode enabled', () => {
      expect(composable.graphState.performance.animationsEnabled).toBe(true)
      expect(composable.graphState.performance.performanceMode).toBe(false)
    })
  })

  describe('updateLayout', () => {
    it('should update layout state', () => {
      composable.updateLayout(LAYOUT_TYPES.HIERARCHICAL)
      expect(composable.graphState.layout).toBe(LAYOUT_TYPES.HIERARCHICAL)
    })

    it('should persist layout to localStorage', () => {
      const setItemSpy = vi.spyOn(localStorage, 'setItem')
      composable.updateLayout(LAYOUT_TYPES.CIRCULAR)
      expect(setItemSpy).toHaveBeenCalledWith('graph-layout-preference', LAYOUT_TYPES.CIRCULAR)
    })

    it('should not update with invalid layout', () => {
      const originalLayout = composable.graphState.layout
      composable.updateLayout('invalid-layout')
      expect(composable.graphState.layout).toBe(originalLayout)
    })
  })

  describe('updateLayoutParam', () => {
    it('should update layout parameter', () => {
      composable.updateLayoutParam(LAYOUT_TYPES.FORCE, 'linkDistance', 100)
      expect(composable.graphState.layoutParams[LAYOUT_TYPES.FORCE].linkDistance).toBe(100)
    })

    it('should not update non-existent layout', () => {
      const originalParams = { ...composable.graphState.layoutParams[LAYOUT_TYPES.FORCE] }
      composable.updateLayoutParam('non-existent', 'param', 100)
      expect(composable.graphState.layoutParams[LAYOUT_TYPES.FORCE]).toEqual(originalParams)
    })
  })

  describe('updateVisualMode', () => {
    it('should update visual mode', () => {
      composable.updateVisualMode(VISUAL_MODES.TWO_D)
      expect(composable.graphState.visualMode).toBe(VISUAL_MODES.TWO_D)
    })

    it('should not update with invalid visual mode', () => {
      const originalMode = composable.graphState.visualMode
      composable.updateVisualMode('invalid-mode')
      expect(composable.graphState.visualMode).toBe(originalMode)
    })
  })

  describe('updateRenderMode', () => {
    it('should update render mode', () => {
      composable.updateRenderMode(RENDER_MODES.CANVAS)
      expect(composable.graphState.renderMode).toBe(RENDER_MODES.CANVAS)
    })

    it('should not update with invalid render mode', () => {
      const originalMode = composable.graphState.renderMode
      composable.updateRenderMode('invalid-mode')
      expect(composable.graphState.renderMode).toBe(originalMode)
    })
  })

  describe('updateSelection', () => {
    it('should update selection nodes array', () => {
      composable.updateSelection({ nodes: ['node1', 'node2'] })
      expect(composable.graphState.selection.nodes).toEqual(['node1', 'node2'])
    })

    it('should convert single node to array', () => {
      composable.updateSelection({ nodes: 'node1' })
      expect(composable.graphState.selection.nodes).toEqual(['node1'])
    })

    it('should update selection mode', () => {
      composable.updateSelection({ mode: INTERACTION_MODES.PATH })
      expect(composable.graphState.selection.mode).toBe(INTERACTION_MODES.PATH)
    })

    it('should update path start and end', () => {
      composable.updateSelection({
        pathStart: 'node1',
        pathEnd: 'node2'
      })
      expect(composable.graphState.selection.pathStart).toBe('node1')
      expect(composable.graphState.selection.pathEnd).toBe('node2')
    })

    it('should update neighbor hops', () => {
      composable.updateSelection({ neighborHops: 3 })
      expect(composable.graphState.selection.neighborHops).toBe(3)
    })
  })

  describe('addNodeToSelection', () => {
    it('should add node to selection', () => {
      composable.addNodeToSelection('node1')
      expect(composable.graphState.selection.nodes).toContain('node1')
    })

    it('should not add duplicate nodes', () => {
      composable.addNodeToSelection('node1')
      composable.addNodeToSelection('node1')
      expect(composable.graphState.selection.nodes).toEqual(['node1'])
    })

    it('should respect max 10 nodes limit', () => {
      // Add 10 nodes
      for (let i = 0; i < 10; i++) {
        composable.addNodeToSelection(`node${i}`)
      }
      // Try to add 11th node
      composable.addNodeToSelection('node10')
      expect(composable.graphState.selection.nodes.length).toBe(10)
      expect(composable.graphState.selection.nodes).not.toContain('node10')
    })
  })

  describe('removeNodeFromSelection', () => {
    it('should remove node from selection', () => {
      composable.updateSelection({ nodes: ['node1', 'node2', 'node3'] })
      composable.removeNodeFromSelection('node2')
      expect(composable.graphState.selection.nodes).toEqual(['node1', 'node3'])
    })

    it('should handle removing non-existent node', () => {
      const originalNodes = [...composable.graphState.selection.nodes]
      composable.removeNodeFromSelection('non-existent')
      expect(composable.graphState.selection.nodes).toEqual(originalNodes)
    })
  })

  describe('clearSelection', () => {
    it('should clear all selected nodes', () => {
      composable.updateSelection({ nodes: ['node1', 'node2'] })
      composable.clearSelection()
      expect(composable.graphState.selection.nodes).toEqual([])
    })

    it('should clear path state', () => {
      composable.updateSelection({
        nodes: ['node1'],
        pathStart: 'node1',
        pathEnd: 'node2'
      })
      composable.clearSelection()
      expect(composable.graphState.selection.nodes).toEqual([])
      expect(composable.graphState.selection.pathStart).toBeNull()
      expect(composable.graphState.selection.pathEnd).toBeNull()
    })
  })

  describe('updateView', () => {
    it('should update zoom level', () => {
      composable.updateView({ zoom: 2 })
      expect(composable.graphState.view.zoom).toBe(2)
    })

    it('should update pan position', () => {
      composable.updateView({ pan: { x: 100, y: 200 } })
      expect(composable.graphState.view.pan).toEqual({ x: 100, y: 200 })
    })

    it('should update viewport bounds', () => {
      composable.updateView({
        viewport: { x: 10, y: 20, w: 400, h: 300 }
      })
      expect(composable.graphState.view.viewport).toEqual({ x: 10, y: 20, w: 400, h: 300 })
    })

    it('should merge partial updates', () => {
      composable.updateView({ zoom: 1.5 })
      expect(composable.graphState.view.zoom).toBe(1.5)
      expect(composable.graphState.view.pan).toEqual({ x: 0, y: 0 })
    })
  })

  describe('toggleCluster', () => {
    it('should add cluster to expanded set when collapsed', () => {
      composable.toggleCluster('cluster1')
      expect(composable.graphState.clustering.expandedClusters.has('cluster1')).toBe(true)
    })

    it('should remove cluster from expanded set when expanded', () => {
      composable.toggleCluster('cluster1')
      composable.toggleCluster('cluster1')
      expect(composable.graphState.clustering.expandedClusters.has('cluster1')).toBe(false)
    })
  })

  describe('updateClustering', () => {
    it('should update clustering enabled state', () => {
      composable.updateClustering({ enabled: true })
      expect(composable.graphState.clustering.enabled).toBe(true)
    })

    it('should update auto-detect state', () => {
      composable.updateClustering({ autoDetect: false })
      expect(composable.graphState.clustering.autoDetect).toBe(false)
    })

    it('should merge partial updates', () => {
      composable.updateClustering({ enabled: true })
      expect(composable.graphState.clustering.enabled).toBe(true)
      expect(composable.graphState.clustering.autoDetect).toBe(true) // unchanged
    })
  })

  describe('updatePerformanceMode', () => {
    it('should enable performance mode', () => {
      composable.updatePerformanceMode(true)
      expect(composable.graphState.performance.performanceMode).toBe(true)
      expect(composable.graphState.performance.animationsEnabled).toBe(false)
    })

    it('should disable performance mode', () => {
      composable.updatePerformanceMode(false)
      expect(composable.graphState.performance.performanceMode).toBe(false)
      expect(composable.graphState.performance.animationsEnabled).toBe(true)
    })
  })

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      // Modify some state
      composable.updateLayout(LAYOUT_TYPES.HIERARCHICAL)
      composable.updateSelection({ nodes: ['node1'] })
      composable.updateView({ zoom: 2 })

      // Reset
      composable.reset()

      // Verify reset
      expect(composable.graphState.layout).toBe(LAYOUT_TYPES.FORCE)
      expect(composable.graphState.selection.nodes).toEqual([])
      expect(composable.graphState.view.zoom).toBe(1)
    })
  })

  describe('updatePathResult', () => {
    it('should update pathResult with array', () => {
      composable.updatePathResult(['node1', 'node2', 'node3'])
      expect(composable.graphState.selection.pathResult).toEqual(['node1', 'node2', 'node3'])
    })

    it('should reset pathResult with empty array for non-array input', () => {
      composable.updatePathResult(null)
      expect(composable.graphState.selection.pathResult).toEqual([])
    })
  })

  describe('updateNeighborResult', () => {
    it('should update neighborResult with array', () => {
      composable.updateNeighborResult(['nodeA', 'nodeB'])
      expect(composable.graphState.selection.neighborResult).toEqual(['nodeA', 'nodeB'])
    })
  })

  describe('interactionMeta', () => {
    it('should return default meta for select mode', () => {
      expect(composable.interactionMeta.value.cursor).toBe('pointer')
      expect(composable.interactionMeta.value.instruction).toBeNull()
    })

    it('should return path mode meta', () => {
      composable.updateSelection({ mode: INTERACTION_MODES.PATH })
      expect(composable.interactionMeta.value.cursor).toBe('crosshair')
      expect(composable.interactionMeta.value.instruction).toBe('Click two nodes to find shortest path')
    })

    it('should return neighbor mode meta', () => {
      composable.updateSelection({ mode: INTERACTION_MODES.NEIGHBOR })
      expect(composable.interactionMeta.value.cursor).toBe('cell')
    })

    it('should return lasso mode meta', () => {
      composable.updateSelection({ mode: INTERACTION_MODES.LASSO })
      expect(composable.interactionMeta.value.cursor).toBe('crosshair')
      expect(composable.interactionMeta.value.instruction).toBe('Click and drag to select multiple nodes')
    })
  })

  describe('updateRenderMode with user selection flag', () => {
    it('should set _userSelectedRenderMode when isUserSelection is true', () => {
      composable.updateRenderMode(RENDER_MODES.CANVAS, true)
      expect(composable.graphState.renderMode).toBe(RENDER_MODES.CANVAS)
      expect(composable.graphState._userSelectedRenderMode).toBe(true)
    })

    it('should not set flag when isUserSelection is false', () => {
      composable.updateRenderMode(RENDER_MODES.SVG, false)
      expect(composable.graphState._userSelectedRenderMode).toBe(false)
    })
  })

  describe('reactive behavior', () => {
    it('should make graphState reactive', () => {
      const initialState = composable.graphState.layout
      composable.updateLayout(LAYOUT_TYPES.CIRCULAR)
      expect(composable.graphState.layout).toBe(LAYOUT_TYPES.CIRCULAR)
      expect(composable.graphState.layout).not.toBe(initialState)
    })

    it('should maintain immutability of arrays', () => {
      const originalArray = composable.graphState.selection.nodes
      composable.updateSelection({ nodes: ['new-node'] })
      expect(composable.graphState.selection.nodes).not.toBe(originalArray)
    })
  })
})
