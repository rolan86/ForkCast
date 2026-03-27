import { describe, it, expect, beforeEach, vi } from 'vitest'
import { effectScope } from 'vue'
import { useGraphRenderer } from '@/composables/useGraphRenderer.js'

// Mock D3
vi.mock('d3', () => ({
  select: vi.fn(() => ({
    selectAll: vi.fn().mockReturnThis(),
    remove: vi.fn().mockReturnThis(),
    append: vi.fn().mockReturnThis(),
    attr: vi.fn().mockReturnThis(),
    call: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    data: vi.fn().mockReturnThis(),
    join: vi.fn().mockReturnThis(),
    each: vi.fn().mockReturnThis(),
    filter: vi.fn().mockReturnThis(),
    classed: vi.fn().mockReturnThis(),
    style: vi.fn().mockReturnThis(),
    transition: vi.fn().mockReturnThis(),
    duration: vi.fn().mockReturnThis(),
    delay: vi.fn().mockReturnThis(),
    node: vi.fn(() => ({})),
    empty: vi.fn(() => false),
    text: vi.fn().mockReturnThis(),
  })),
  zoom: vi.fn(() => ({
    scaleExtent: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    scaleBy: vi.fn(),
    transform: vi.fn(),
  })),
  zoomIdentity: { x: 0, y: 0, k: 1 },
  zoomTransform: vi.fn(() => ({ x: 0, y: 0, k: 1 })),
  drag: vi.fn(() => ({
    on: vi.fn().mockReturnThis(),
  })),
}))

vi.mock('@/utils/graph/layouts/force.js', () => ({
  runForceLayout: vi.fn(() => ({ stop: vi.fn() })),
  runForceLayoutWithEdgeStrength: vi.fn(() => ({
    stop: vi.fn(),
    on: vi.fn().mockReturnThis(),
    alphaTarget: vi.fn().mockReturnThis(),
    restart: vi.fn(),
  })),
}))

vi.mock('@/utils/graph/layouts/hierarchical.js', () => ({
  runHierarchicalLayout: vi.fn((nodes) => ({ nodes: nodes.map(n => ({ ...n, x: 100, y: 100 })) })),
}))

vi.mock('@/utils/graph/layouts/circular.js', () => ({
  runCircularLayout: vi.fn((nodes) => ({ nodes: nodes.map(n => ({ ...n, x: 50, y: 50 })) })),
}))

vi.mock('@/utils/graph/layouts/clustered.js', () => ({
  runClusteredLayout: vi.fn((nodes) => ({
    nodes: nodes.map(n => ({ ...n, x: 75, y: 75 })),
    clustering: { clusterCount: 3 },
  })),
}))

vi.mock('@/utils/graph/rendering/hybridRenderer.js', () => ({
  renderHybrid: vi.fn(() => ({
    nodeSvg: { transition: vi.fn().mockReturnThis(), call: vi.fn().mockReturnThis() },
    zoom: { scaleBy: vi.fn(), transform: vi.fn(), on: vi.fn().mockReturnThis() },
    setSimulation: vi.fn(),
    destroy: vi.fn(),
  })),
}))

describe('useGraphRenderer', () => {
  let renderer
  let scope

  beforeEach(() => {
    scope = effectScope()
    scope.run(() => {
      renderer = useGraphRenderer()
    })
  })

  describe('initialization', () => {
    it('should expose reactive refs', () => {
      expect(renderer.viewport).toBeDefined()
      expect(renderer.viewport.value).toEqual({ x: 0, y: 0, w: 0, h: 0 })
      expect(renderer.connCounts).toBeDefined()
      expect(renderer.connCounts.value).toEqual({})
      expect(renderer.isRendering).toBeDefined()
      expect(renderer.isRendering.value).toBe(false)
      expect(renderer.renderMode).toBeDefined()
      expect(renderer.renderMode.value).toBeNull()
    })

    it('should expose lifecycle methods', () => {
      expect(typeof renderer.bind).toBe('function')
      expect(typeof renderer.destroy).toBe('function')
    })

    it('should expose action methods', () => {
      expect(typeof renderer.render).toBe('function')
      expect(typeof renderer.applyLayout).toBe('function')
      expect(typeof renderer.applySearchFilters).toBe('function')
      expect(typeof renderer.zoomIn).toBe('function')
      expect(typeof renderer.zoomOut).toBe('function')
      expect(typeof renderer.zoomReset).toBe('function')
      expect(typeof renderer.panTo).toBe('function')
      expect(typeof renderer.stopSimulation).toBe('function')
    })
  })

  describe('bind', () => {
    it('should store container reference', () => {
      const container = document.createElement('div')
      Object.defineProperty(container, 'clientWidth', { value: 800 })
      Object.defineProperty(container, 'clientHeight', { value: 600 })

      const mockObserve = vi.fn()
      global.ResizeObserver = vi.fn().mockImplementation(function () {
        this.observe = mockObserve
        this.disconnect = vi.fn()
      })

      renderer.bind(container, vi.fn())
      expect(mockObserve).toHaveBeenCalledWith(container)
    })
  })

  describe('render and connCounts', () => {
    it('should populate connCounts from edges on render', () => {
      const container = document.createElement('div')
      Object.defineProperty(container, 'clientWidth', { value: 800 })
      Object.defineProperty(container, 'clientHeight', { value: 600 })

      global.ResizeObserver = vi.fn().mockImplementation(function () {
        this.observe = vi.fn()
        this.disconnect = vi.fn()
      })

      renderer.bind(container, vi.fn())

      const graphData = {
        nodes: [{ id: 'A', type: 'Person' }, { id: 'B', type: 'Org' }, { id: 'C', type: 'Person' }],
        edges: [{ source: 'A', target: 'B' }, { source: 'B', target: 'C' }],
      }

      renderer.render(graphData, {
        renderMode: 'svg',
        userSelectedRenderMode: true,
        onNodeClick: vi.fn(),
        getNodeColor: vi.fn(() => '#fff'),
        layoutParams: {},
      })

      expect(renderer.connCounts.value.B).toBe(2)
      expect(renderer.connCounts.value.A).toBe(1)
      expect(renderer.connCounts.value.C).toBe(1)
    })
  })

  describe('applyLayout', () => {
    it('should return layout result for static layouts', () => {
      const container = document.createElement('div')
      Object.defineProperty(container, 'clientWidth', { value: 800 })
      Object.defineProperty(container, 'clientHeight', { value: 600 })

      global.ResizeObserver = vi.fn().mockImplementation(function () {
        this.observe = vi.fn()
        this.disconnect = vi.fn()
      })

      renderer.bind(container, vi.fn())

      const graphData = {
        nodes: [{ id: 'A', type: 'Person' }, { id: 'B', type: 'Org' }],
        edges: [{ source: 'A', target: 'B' }],
      }

      const result = renderer.applyLayout('hierarchical', graphData, {})
      expect(result).toBeDefined()
      expect(result.nodes).toBeDefined()
    })

    it('should return undefined for force layout', () => {
      const container = document.createElement('div')
      Object.defineProperty(container, 'clientWidth', { value: 800 })
      Object.defineProperty(container, 'clientHeight', { value: 600 })

      global.ResizeObserver = vi.fn().mockImplementation(function () {
        this.observe = vi.fn()
        this.disconnect = vi.fn()
      })

      renderer.bind(container, vi.fn())

      const result = renderer.applyLayout('force', { nodes: [], edges: [] }, {})
      expect(result).toBeUndefined()
    })
  })

  describe('destroy', () => {
    it('should clean up resources', () => {
      const mockDisconnect = vi.fn()
      global.ResizeObserver = vi.fn().mockImplementation(function () {
        this.observe = vi.fn()
        this.disconnect = mockDisconnect
      })

      const container = document.createElement('div')
      renderer.bind(container, vi.fn())
      renderer.destroy()

      expect(mockDisconnect).toHaveBeenCalled()
    })
  })
})
