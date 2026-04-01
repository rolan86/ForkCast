/**
 * Unit tests for GraphStatsPanel component
 *
 * Tests the statistics display panel for graph metrics
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphStatsPanel from '@/components/graph/GraphStatsPanel.vue'

describe('GraphStatsPanel', () => {
  let wrapper

  const defaultProps = {
    nodeCount: 100,
    edgeCount: 250,
    clusterCount: 5,
    selectedCount: 3,
    layout: 'force',
  }

  beforeEach(() => {
    wrapper = mount(GraphStatsPanel, {
      props: defaultProps,
    })
  })

  describe('props', () => {
    it('should render with all props provided', () => {
      expect(wrapper.find('.graph-stats').exists()).toBe(true)
    })

    it('should accept nodeCount prop', () => {
      expect(wrapper.props('nodeCount')).toBe(100)
    })

    it('should accept edgeCount prop', () => {
      expect(wrapper.props('edgeCount')).toBe(250)
    })

    it('should accept clusterCount prop', () => {
      expect(wrapper.props('clusterCount')).toBe(5)
    })

    it('should accept selectedCount prop', () => {
      expect(wrapper.props('selectedCount')).toBe(3)
    })

    it('should accept layout prop', () => {
      expect(wrapper.props('layout')).toBe('force')
    })

    it('should accept fps prop', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45 },
      })
      expect(fpsWrapper.props('fps')).toBe(45)
    })

    it('should accept visualMode prop', () => {
      const modeWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, visualMode: '3d' },
      })
      expect(modeWrapper.props('visualMode')).toBe('3d')
    })

    it('should use default values for missing props', () => {
      const defaultWrapper = mount(GraphStatsPanel)
      expect(defaultWrapper.props('nodeCount')).toBe(0)
      expect(defaultWrapper.props('edgeCount')).toBe(0)
      expect(defaultWrapper.props('clusterCount')).toBe(0)
      expect(defaultWrapper.props('selectedCount')).toBe(0)
      expect(defaultWrapper.props('layout')).toBe('force')
      expect(defaultWrapper.props('fps')).toBe(null)
      expect(defaultWrapper.props('visualMode')).toBe('2d')
    })
  })

  describe('primary stats', () => {
    it('should display node count with icon', () => {
      const nodeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Nodes')
      )
      expect(nodeStat?.exists()).toBe(true)
      expect(nodeStat?.text()).toContain('100')
    })

    it('should display edge count with icon', () => {
      const edgeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Edges')
      )
      expect(edgeStat?.exists()).toBe(true)
      expect(edgeStat?.text()).toContain('250')
    })

    it('should format large numbers with k suffix', async () => {
      await wrapper.setProps({ nodeCount: 1500 })
      const nodeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Nodes')
      )
      expect(nodeStat?.text()).toContain('1.5k')
    })
  })

  describe('secondary stats', () => {
    it('should display cluster count when greater than 0', () => {
      const clusterStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Clusters')
      )
      expect(clusterStat?.exists()).toBe(true)
      expect(clusterStat?.text()).toContain('5')
    })

    it('should not display cluster count when 0', async () => {
      await wrapper.setProps({ clusterCount: 0 })
      const clusterStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Clusters')
      )
      expect(clusterStat).toBeUndefined()
    })

    it('should display selected count when greater than 0', () => {
      const selectedStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Selected')
      )
      expect(selectedStat?.exists()).toBe(true)
      expect(selectedStat?.text()).toContain('3')
    })

    it('should not display selected count when 0', async () => {
      await wrapper.setProps({ selectedCount: 0 })
      const selectedStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Selected')
      )
      expect(selectedStat).toBeUndefined()
    })

    it('should apply highlight styling to selected stat', () => {
      const selectedStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Selected')
      )
      expect(selectedStat?.classes()).toContain('highlight')
    })

    it('should display layout type', () => {
      const layoutStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Layout')
      )
      expect(layoutStat?.exists()).toBe(true)
      expect(layoutStat?.text()).toContain('force')
    })

    it('should display average connections', () => {
      const connStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('Avg Conn')
      )
      expect(connStat?.exists()).toBe(true)
    })
  })

  describe('FPS display (3D mode)', () => {
    it('should not display FPS when visualMode is 2d', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45, visualMode: '2d' },
      })
      const fpsStat = fpsWrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('FPS')
      )
      expect(fpsStat).toBeUndefined()
    })

    it('should not display FPS when fps is null', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: null, visualMode: '3d' },
      })
      const fpsStat = fpsWrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('FPS')
      )
      expect(fpsStat).toBeUndefined()
    })

    it('should display FPS when in 3d mode with fps value', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45, visualMode: '3d' },
      })
      const fpsStat = fpsWrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('FPS')
      )
      expect(fpsStat?.exists()).toBe(true)
      expect(fpsStat?.text()).toContain('45')
    })

    it('should round FPS value for display', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45.7, visualMode: '3d' },
      })
      const fpsStat = fpsWrapper.findAll('.stat.secondary').find(
        stat => stat.text().includes('FPS')
      )
      expect(fpsStat?.text()).toContain('46')
    })

    it('should apply fps-low class when fps < 20', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 15, visualMode: '3d' },
      })
      const fpsValue = fpsWrapper.find('.fps-low')
      expect(fpsValue.exists()).toBe(true)
      expect(fpsValue.text()).toContain('15')
    })

    it('should not apply fps-low class when fps >= 20', () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 30, visualMode: '3d' },
      })
      const fpsValue = fpsWrapper.findAll('.stat-value').find(
        val => val.text().includes('30')
      )
      expect(fpsValue?.classes()).not.toContain('fps-low')
    })

    it('should update FPS display reactively', async () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45, visualMode: '3d' },
      })
      expect(fpsWrapper.text()).toContain('45')

      await fpsWrapper.setProps({ fps: 30 })
      expect(fpsWrapper.text()).toContain('30')
    })
  })

  describe('icons', () => {
    it('should display lucide icons for stats', () => {
      const icons = wrapper.findAll('.stat-icon')
      expect(icons.length).toBeGreaterThan(0)
    })
  })

  describe('stat value formatting', () => {
    it('should format numbers below 1000 as-is', async () => {
      await wrapper.setProps({ nodeCount: 999 })
      const nodeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Nodes')
      )
      expect(nodeStat?.text()).toContain('999')
    })

    it('should format 1000 as 1.0k', async () => {
      await wrapper.setProps({ nodeCount: 1000 })
      const nodeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Nodes')
      )
      expect(nodeStat?.text()).toContain('1.0k')
    })

    it('should format large numbers correctly', async () => {
      await wrapper.setProps({ nodeCount: 15000 })
      const nodeStat = wrapper.findAll('.stat.primary').find(
        stat => stat.text().includes('Nodes')
      )
      expect(nodeStat?.text()).toContain('15.0k')
    })
  })

  describe('styling', () => {
    it('should apply glass morphism styling', () => {
      const statsPanel = wrapper.find('.graph-stats')
      expect(statsPanel.classes()).toContain('graph-stats')
    })

    it('should apply primary stat styling', () => {
      const primaryStats = wrapper.findAll('.stat.primary')
      expect(primaryStats.length).toBe(2)
      primaryStats.forEach(stat => {
        expect(stat.classes()).toContain('primary')
      })
    })

    it('should apply secondary stat styling', () => {
      const secondaryStats = wrapper.findAll('.stat.secondary')
      expect(secondaryStats.length).toBeGreaterThan(0)
      secondaryStats.forEach(stat => {
        expect(stat.classes()).toContain('secondary')
      })
    })

    it('should apply highlight styling to selected count', () => {
      const selectedStat = wrapper.findAll('.stat.secondary').find(
        stat => stat.classes().includes('highlight')
      )
      expect(selectedStat?.exists()).toBe(true)
    })
  })

  describe('layout', () => {
    it('should display stats in rows', () => {
      const rows = wrapper.findAll('.stats-row')
      expect(rows.length).toBe(2)
    })

    it('should have primary stats in first row', () => {
      const firstRow = wrapper.findAll('.stats-row')[0]
      const primaryStats = firstRow.findAll('.stat.primary')
      expect(primaryStats.length).toBe(2)
    })

    it('should have secondary stats in second row', () => {
      const secondRow = wrapper.findAll('.stats-row')[1]
      const secondaryStats = secondRow.findAll('.stat.secondary')
      expect(secondaryStats.length).toBeGreaterThan(0)
    })
  })

  describe('empty state', () => {
    it('should display zeros when no data', () => {
      const emptyWrapper = mount(GraphStatsPanel, {
        props: {
          nodeCount: 0,
          edgeCount: 0,
          clusterCount: 0,
          selectedCount: 0,
        },
      })
      expect(emptyWrapper.text()).toContain('0')
    })

    it('should still show layout when other stats are 0', () => {
      const emptyWrapper = mount(GraphStatsPanel, {
        props: {
          nodeCount: 0,
          edgeCount: 0,
          clusterCount: 0,
          selectedCount: 0,
          layout: 'hierarchical',
        },
      })
      expect(emptyWrapper.text()).toContain('hierarchical')
    })
  })

  describe('reactivity', () => {
    it('should update display when props change', async () => {
      expect(wrapper.text()).toContain('100')
      await wrapper.setProps({ nodeCount: 200 })
      expect(wrapper.text()).toContain('200')
    })

    it('should show/hide cluster stat based on prop', async () => {
      await wrapper.setProps({ clusterCount: 5 })
      expect(wrapper.text()).toContain('Clusters')

      await wrapper.setProps({ clusterCount: 0 })
      expect(wrapper.text()).not.toContain('Clusters')
    })

    it('should show/hide selected stat based on prop', async () => {
      await wrapper.setProps({ selectedCount: 3 })
      expect(wrapper.text()).toContain('Selected')

      await wrapper.setProps({ selectedCount: 0 })
      expect(wrapper.text()).not.toContain('Selected')
    })

    it('should show/hide FPS stat based on visualMode and fps', async () => {
      const fpsWrapper = mount(GraphStatsPanel, {
        props: { ...defaultProps, fps: 45, visualMode: '2d' },
      })
      expect(fpsWrapper.text()).not.toContain('FPS')

      await fpsWrapper.setProps({ visualMode: '3d' })
      expect(fpsWrapper.text()).toContain('45')

      await fpsWrapper.setProps({ fps: null })
      expect(fpsWrapper.text()).not.toContain('FPS')
    })
  })
})
