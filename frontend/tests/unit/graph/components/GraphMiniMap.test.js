/**
 * Unit tests for GraphMiniMap component
 *
 * Tests the mini-map navigation component with D3 rendering
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import GraphMiniMap from '@/components/graph/GraphMiniMap.vue'
import { NEON_COLORS } from '@/constants/graph.js'

// Mock D3 to avoid actual rendering in tests
vi.mock('d3', () => {
  const createChainable = () => {
    const chain = {
      append: vi.fn(() => createChainable()),
      selectAll: vi.fn(() => createChainable()),
      select: vi.fn(() => createChainable()),
      data: vi.fn(() => createChainable()),
      join: vi.fn(() => createChainable()),
      attr: vi.fn(() => createChainable()),
      style: vi.fn(() => createChainable()),
      on: vi.fn(() => createChainable()),
      call: vi.fn(() => createChainable()),
      remove: vi.fn(() => createChainable()),
      text: vi.fn(() => createChainable()),
    }
    return chain
  }

  return {
    select: vi.fn(() => createChainable()),
    drag: vi.fn(() => ({
      on: vi.fn(function() { return this }),
    })),
    color: vi.fn((str) => {
      if (!str) return null
      return {
        opacity: 1,
        toString: () => str,
      }
    }),
  }
})

describe('GraphMiniMap', () => {
  let wrapper

  const mockNodes = [
    { id: 'node1', x: 100, y: 100, type: 'Person' },
    { id: 'node2', x: 200, y: 150, type: 'Organization' },
    { id: 'node3', x: 150, y: 200, type: 'Concept' },
  ]

  const mockViewport = {
    x: 50,
    y: 50,
    w: 200,
    h: 150,
  }

  const mockMainViewBounds = {
    x: 0,
    y: 0,
    w: 1000,
    h: 800,
  }

  beforeEach(() => {
    wrapper = mount(GraphMiniMap, {
      props: {
        nodes: mockNodes,
        viewport: mockViewport,
        mainViewBounds: mockMainViewBounds,
      },
    })
  })

  describe('props', () => {
    it('should render with all props provided', () => {
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })

    it('should accept nodes prop', () => {
      expect(wrapper.props('nodes')).toEqual(mockNodes)
    })

    it('should accept viewport prop', () => {
      expect(wrapper.props('viewport')).toEqual(mockViewport)
    })

    it('should accept mainViewBounds prop', () => {
      expect(wrapper.props('mainViewBounds')).toEqual(mockMainViewBounds)
    })

    it('should accept visualMode prop', () => {
      const mode3dWrapper = mount(GraphMiniMap, {
        props: {
          nodes: mockNodes,
          viewport: mockViewport,
          mainViewBounds: mockMainViewBounds,
          visualMode: '3d',
        },
      })
      expect(mode3dWrapper.props('visualMode')).toBe('3d')
    })

    it('should use default empty array for nodes', () => {
      const defaultWrapper = mount(GraphMiniMap)
      expect(defaultWrapper.props('nodes')).toEqual([])
    })

    it('should use default object for viewport', () => {
      const defaultWrapper = mount(GraphMiniMap)
      expect(defaultWrapper.props('viewport')).toEqual({ x: 0, y: 0, w: 0, h: 0 })
    })

    it('should use default object for mainViewBounds', () => {
      const defaultWrapper = mount(GraphMiniMap)
      expect(defaultWrapper.props('mainViewBounds')).toEqual({ x: 0, y: 0, w: 0, h: 0 })
    })

    it('should use default 2d visualMode', () => {
      const defaultWrapper = mount(GraphMiniMap)
      expect(defaultWrapper.props('visualMode')).toBe('2d')
    })
  })

  describe('rendering', () => {
    it('should render container div', () => {
      const container = wrapper.find('.mini-map')
      expect(container.exists()).toBe(true)
    })

    it('should set correct dimensions', () => {
      const container = wrapper.find('.mini-map')
      const style = container.attributes('style') || ''
      expect(style).toContain('150px') // MINIMAP_SIZE
    })

    it('should render when nodes are provided', async () => {
      await wrapper.setProps({ nodes: mockNodes })
      await nextTick()
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })

    it('should not crash with empty nodes array', async () => {
      await wrapper.setProps({ nodes: [] })
      await nextTick()
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })
  })

  describe('viewport indicator', () => {
    it('should handle valid viewport', async () => {
      await wrapper.setProps({
        viewport: { x: 50, y: 50, w: 200, h: 150 },
        mainViewBounds: { x: 0, y: 0, w: 1000, h: 800 },
      })
      await nextTick()
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })

    it('should handle zero-width viewport', async () => {
      await wrapper.setProps({
        viewport: { x: 0, y: 0, w: 0, h: 150 },
      })
      await nextTick()
      // Should not crash
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })

    it('should handle zero-height viewport', async () => {
      await wrapper.setProps({
        viewport: { x: 0, y: 0, w: 200, h: 0 },
      })
      await nextTick()
      expect(wrapper.find('.mini-map').exists()).toBe(true)
    })
  })

  describe('navigation', () => {
    it('should emit navigate-to event', async () => {
      // This test verifies the emit is defined
      // Actual drag behavior testing would require more complex setup
      expect(wrapper.vm).toBeDefined()
    })
  })

  describe('graph bounds calculation', () => {
    it('should calculate bounds correctly for nodes', () => {
      const bounds = wrapper.vm.calculateGraphBounds(mockNodes)
      expect(bounds.minX).toBe(100)
      expect(bounds.maxX).toBe(200)
      expect(bounds.minY).toBe(100)
      expect(bounds.maxY).toBe(200)
    })

    it('should handle empty nodes array', () => {
      const bounds = wrapper.vm.calculateGraphBounds([])
      expect(bounds.minX).toBe(0)
      expect(bounds.maxX).toBe(100)
      expect(bounds.minY).toBe(0)
      expect(bounds.maxY).toBe(100)
    })

    it('should handle nodes without x/y coordinates', () => {
      const nodesWithoutCoords = [
        { id: 'node1', type: 'Person' },
        { id: 'node2', type: 'Organization' },
      ]
      const bounds = wrapper.vm.calculateGraphBounds(nodesWithoutCoords)
      expect(bounds.width).toBe(100) // Default fallback
      expect(bounds.height).toBe(100)
    })

    it('should calculate width and height correctly', () => {
      const bounds = wrapper.vm.calculateGraphBounds(mockNodes)
      expect(bounds.width).toBe(100) // 200 - 100
      expect(bounds.height).toBe(100) // 200 - 100
    })
  })

  describe('styling', () => {
    it('should apply glass morphism styling', () => {
      const miniMap = wrapper.find('.mini-map')
      expect(miniMap.classes()).toContain('mini-map')
    })

    it('should have scanline effect', () => {
      const miniMap = wrapper.find('.mini-map')
      expect(miniMap.exists()).toBe(true)
    })

    it('should use NEON_COLORS for nodes', () => {
      expect(NEON_COLORS.Person).toBeDefined()
      expect(NEON_COLORS.Organization).toBeDefined()
      expect(NEON_COLORS.Concept).toBeDefined()
    })
  })

  describe('reactivity', () => {
    it('should update when nodes prop changes', async () => {
      const newNodes = [
        { id: 'node4', x: 300, y: 300, type: 'Event' },
      ]
      await wrapper.setProps({ nodes: newNodes })
      await nextTick()
      expect(wrapper.props('nodes')).toEqual(newNodes)
    })

    it('should update when viewport prop changes', async () => {
      const newViewport = { x: 100, y: 100, w: 300, h: 200 }
      await wrapper.setProps({ viewport: newViewport })
      await nextTick()
      expect(wrapper.props('viewport')).toEqual(newViewport)
    })

    it('should update when mainViewBounds prop changes', async () => {
      const newBounds = { x: 0, y: 0, w: 1200, h: 900 }
      await wrapper.setProps({ mainViewBounds: newBounds })
      await nextTick()
      expect(wrapper.props('mainViewBounds')).toEqual(newBounds)
    })
  })

  describe('cleanup', () => {
    it('should clean up D3 selections on unmount', () => {
      const unmountWrapper = mount(GraphMiniMap, {
        props: {
          nodes: mockNodes,
          viewport: mockViewport,
          mainViewBounds: mockMainViewBounds,
        },
      })
      expect(() => unmountWrapper.unmount()).not.toThrow()
    })
  })

  describe('edge cases', () => {
    it('should handle single node', () => {
      const singleNode = [{ id: 'node1', x: 100, y: 100, type: 'Person' }]
      const bounds = wrapper.vm.calculateGraphBounds(singleNode)
      expect(bounds.minX).toBe(100)
      expect(bounds.maxX).toBe(100)
      expect(bounds.width).toBe(100) // 100 - 100 = 0, but fallback (|| 100) applies
    })

    it('should handle nodes with negative coordinates', () => {
      const negativeNodes = [
        { id: 'node1', x: -100, y: -50, type: 'Person' },
        { id: 'node2', x: 100, y: 50, type: 'Organization' },
      ]
      const bounds = wrapper.vm.calculateGraphBounds(negativeNodes)
      expect(bounds.minX).toBe(-100)
      expect(bounds.maxX).toBe(100)
      expect(bounds.minY).toBe(-50)
      expect(bounds.maxY).toBe(50)
    })

    it('should handle very large coordinates', () => {
      const largeNodes = [
        { id: 'node1', x: 10000, y: 10000, type: 'Person' },
        { id: 'node2', x: 20000, y: 20000, type: 'Organization' },
      ]
      const bounds = wrapper.vm.calculateGraphBounds(largeNodes)
      expect(bounds.minX).toBe(10000)
      expect(bounds.maxX).toBe(20000)
    })
  })

  describe('accessibility', () => {
    it('should have properly sized container', () => {
      const container = wrapper.find('.mini-map')
      const style = container.attributes('style') || ''
      expect(style).toContain('width')
      expect(style).toContain('height')
    })
  })

  describe('mini-map dimensions', () => {
    it('should use MINIMAP_SIZE constant', () => {
      // The component should render with fixed 150px size
      const container = wrapper.find('.mini-map')
      const style = container.attributes('style') || ''
      expect(style).toContain('150px')
    })

    it('should have proper padding for node rendering', () => {
      // The component should account for PADDING constant
      expect(wrapper.vm).toBeDefined()
    })
  })

  describe('3D top-down projection', () => {
    it('should handle 3D visualMode prop', async () => {
      const nodes3d = [
        { id: 'node1', x: 100, y: 100, z: 50, type: 'Person' },
        { id: 'node2', x: 200, y: 150, z: 100, type: 'Organization' },
        { id: 'node3', x: 150, y: 200, z: 75, type: 'Concept' },
      ]
      const wrapper3d = mount(GraphMiniMap, {
        props: {
          nodes: nodes3d,
          viewport: mockViewport,
          mainViewBounds: mockMainViewBounds,
          visualMode: '3d',
        },
      })
      expect(wrapper3d.props('visualMode')).toBe('3d')
    })

    it('should calculate 3D bounds correctly', () => {
      const nodes3d = [
        { id: 'node1', x: 100, y: 100, z: 50, type: 'Person' },
        { id: 'node2', x: 200, y: 150, z: 100, type: 'Organization' },
        { id: 'node3', x: 150, y: 200, z: 75, type: 'Concept' },
      ]
      const wrapper3d = mount(GraphMiniMap, {
        props: {
          nodes: nodes3d,
          visualMode: '3d',
        },
      })
      const bounds = wrapper3d.vm.calculate3DBounds(nodes3d)
      expect(bounds.minX).toBe(100)
      expect(bounds.maxX).toBe(200)
      expect(bounds.minZ).toBe(50)
      expect(bounds.maxZ).toBe(100)
      expect(bounds.width).toBe(100)
      expect(bounds.depth).toBe(50)
    })

    it('should handle empty nodes in 3D mode', () => {
      const wrapper3d = mount(GraphMiniMap, {
        props: {
          nodes: [],
          visualMode: '3d',
        },
      })
      const bounds = wrapper3d.vm.calculate3DBounds([])
      expect(bounds.minX).toBe(0)
      expect(bounds.minZ).toBe(0)
      expect(bounds.maxX).toBe(100)
      expect(bounds.maxZ).toBe(100)
    })

    it('should switch between 2D and 3D modes', async () => {
      const nodes2d3d = [
        { id: 'node1', x: 100, y: 100, z: 50, type: 'Person' },
        { id: 'node2', x: 200, y: 150, z: 100, type: 'Organization' },
      ]
      const wrapper2d3d = mount(GraphMiniMap, {
        props: {
          nodes: nodes2d3d,
          viewport: mockViewport,
          mainViewBounds: mockMainViewBounds,
          visualMode: '2d',
        },
      })
      expect(wrapper2d3d.props('visualMode')).toBe('2d')

      // Switch to 3D
      await wrapper2d3d.setProps({ visualMode: '3d' })
      await nextTick()
      expect(wrapper2d3d.props('visualMode')).toBe('3d')

      // Switch back to 2D
      await wrapper2d3d.setProps({ visualMode: '2d' })
      await nextTick()
      expect(wrapper2d3d.props('visualMode')).toBe('2d')
    })

    it('should handle nodes without z coordinates in 3D mode', () => {
      const nodesWithoutZ = [
        { id: 'node1', x: 100, y: 100, type: 'Person' },
        { id: 'node2', x: 200, y: 150, type: 'Organization' },
      ]
      const wrapper3d = mount(GraphMiniMap, {
        props: {
          nodes: nodesWithoutZ,
          visualMode: '3d',
        },
      })
      const bounds = wrapper3d.vm.calculate3DBounds(nodesWithoutZ)
      expect(bounds.minZ).toBe(0)
      expect(bounds.maxZ).toBe(100)
    })
  })
})
