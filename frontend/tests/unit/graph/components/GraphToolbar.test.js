/**
 * Unit tests for GraphToolbar component
 *
 * Tests the toolbar controls for layout, modes, clustering, and view options
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphToolbar from '@/components/graph/GraphToolbar.vue'
import { LAYOUT_TYPES, INTERACTION_MODES, VISUAL_MODES } from '@/constants/graph.js'

describe('GraphToolbar', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(GraphToolbar, {
      props: {
        currentLayout: LAYOUT_TYPES.FORCE,
        currentMode: INTERACTION_MODES.SELECT,
        clusteringEnabled: false,
        canExpandClusters: false,
        visualMode: VISUAL_MODES.TWO_POINT_FIVE_D,
      },
    })
  })

  describe('props', () => {
    it('should render with default props', () => {
      expect(wrapper.find('.graph-toolbar').exists()).toBe(true)
    })

    it('should accept currentLayout prop', () => {
      await wrapper.setProps({ currentLayout: LAYOUT_TYPES.HIERARCHICAL })
      expect(wrapper.props('currentLayout')).toBe(LAYOUT_TYPES.HIERARCHICAL)
    })

    it('should accept currentMode prop', () => {
      await wrapper.setProps({ currentMode: INTERACTION_MODES.PATH })
      expect(wrapper.props('currentMode')).toBe(INTERACTION_MODES.PATH)
    })

    it('should accept clusteringEnabled prop', () => {
      await wrapper.setProps({ clusteringEnabled: true })
      expect(wrapper.props('clusteringEnabled')).toBe(true)
    })

    it('should accept visualMode prop', () => {
      await wrapper.setProps({ visualMode: VISUAL_MODES.TWO_D })
      expect(wrapper.props('visualMode')).toBe(VISUAL_MODES.TWO_D)
    })
  })

  describe('layout selector', () => {
    it('should render all layout options', () => {
      const layoutButtons = wrapper.findAll('.layout-button')
      expect(layoutButtons).toHaveLength(Object.values(LAYOUT_TYPES).length)
    })

    it('should mark current layout as active', () => {
      await wrapper.setProps({ currentLayout: LAYOUT_TYPES.FORCE })
      const forceButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Force')
      )
      expect(forceButton?.classes()).toContain('active')
    })

    it('should emit select-layout when clicking layout button', async () => {
      const forceButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Force')
      )
      await forceButton?.trigger('click')
      expect(wrapper.emitted('select-layout')).toBeTruthy()
      expect(wrapper.emitted('select-layout')?.[0]).toEqual([LAYOUT_TYPES.FORCE])
    })

    it('should switch active layout when prop changes', async () => {
      await wrapper.setProps({ currentLayout: LAYOUT_TYPES.FORCE })
      let forceButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Force')
      )
      expect(forceButton?.classes()).toContain('active')

      await wrapper.setProps({ currentLayout: LAYOUT_TYPES.CIRCULAR })
      forceButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Force')
      )
      expect(forceButton?.classes()).not.toContain('active')

      const circularButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Circular')
      )
      expect(circularButton?.classes()).toContain('active')
    })
  })

  describe('interaction mode buttons', () => {
    it('should render all mode options', () => {
      const modeButtons = wrapper.findAll('.mode-button')
      expect(modeButtons).toHaveLength(Object.values(INTERACTION_MODES).length)
    })

    it('should mark current mode as active', () => {
      await wrapper.setProps({ currentMode: INTERACTION_MODES.SELECT })
      const selectButton = wrapper.findAll('.mode-button')[0]
      expect(selectButton.classes()).toContain('active')
    })

    it('should emit select-mode when clicking mode button', async () => {
      const selectButton = wrapper.findAll('.mode-button')[0]
      await selectButton.trigger('click')
      expect(wrapper.emitted('select-mode')).toBeTruthy()
    })

    it('should render mode icons', () => {
      const modeButtons = wrapper.findAll('.mode-button')
      modeButtons.forEach(button => {
        expect(button.find('svg').exists()).toBe(true)
      })
    })
  })

  describe('visual mode toggle', () => {
    it('should render 2.5D toggle button', () => {
      const toggleButton = wrapper.find('.visual-toggle')
      expect(toggleButton.exists()).toBe(true)
      expect(toggleButton.text()).toContain('2.5D')
    })

    it('should mark 2.5D mode as active when enabled', async () => {
      await wrapper.setProps({ visualMode: VISUAL_MODES.TWO_POINT_FIVE_D })
      const toggleButton = wrapper.find('.visual-toggle')
      expect(toggleButton.classes()).toContain('active')
    })

    it('should not mark 2.5D mode as active when in 2D mode', async () => {
      await wrapper.setProps({ visualMode: VISUAL_MODES.TWO_D })
      const toggleButton = wrapper.find('.visual-toggle')
      expect(toggleButton.classes()).not.toContain('active')
    })

    it('should emit toggle-visual-mode when clicked', async () => {
      const toggleButton = wrapper.find('.visual-toggle')
      await toggleButton.trigger('click')
      expect(wrapper.emitted('toggle-visual-mode')).toBeTruthy()
    })
  })

  describe('clustering controls', () => {
    it('should not render clustering controls when both props are false', () => {
      expect(wrapper.find('.toolbar-group[v-if]').exists()).toBe(false)
    })

    it('should render clustering controls when clusteringEnabled is true', async () => {
      await wrapper.setProps({ clusteringEnabled: true })
      expect(wrapper.find('.cluster-toggle').exists()).toBe(true)
    })

    it('should render clustering controls when canExpandClusters is true', async () => {
      await wrapper.setProps({ canExpandClusters: true })
      expect(wrapper.find('.cluster-toggle').exists()).toBe(true)
    })

    it('should mark Auto button as active when clustering is enabled', async () => {
      await wrapper.setProps({ clusteringEnabled: true })
      const autoButton = wrapper.find('.cluster-toggle')
      expect(autoButton.classes()).toContain('active')
    })

    it('should emit toggle-clustering when clicking Auto button', async () => {
      await wrapper.setProps({ clusteringEnabled: false })
      await wrapper.setProps({ canExpandClusters: true })

      const autoButton = wrapper.find('.cluster-toggle')
      await autoButton.trigger('click')
      expect(wrapper.emitted('toggle-clustering')).toBeTruthy()
    })

    it('should render Expand and Collapse buttons when clustering is enabled', async () => {
      await wrapper.setProps({ clusteringEnabled: true })
      const actionButtons = wrapper.findAll('.cluster-action')
      expect(actionButtons).toHaveLength(2)
      expect(actionButtons[0].text()).toContain('Expand')
      expect(actionButtons[1].text()).toContain('Collapse')
    })

    it('should emit expand-all when clicking Expand button', async () => {
      await wrapper.setProps({ clusteringEnabled: true })
      const expandButton = wrapper.findAll('.cluster-action').find(
        btn => btn.text().includes('Expand')
      )
      await expandButton?.trigger('click')
      expect(wrapper.emitted('expand-all')).toBeTruthy()
    })

    it('should emit collapse-all when clicking Collapse button', async () => {
      await wrapper.setProps({ clusteringEnabled: true })
      const collapseButton = wrapper.findAll('.cluster-action').find(
        btn => btn.text().includes('Collapse')
      )
      await collapseButton?.trigger('click')
      expect(wrapper.emitted('collapse-all')).toBeTruthy()
    })
  })

  describe('view controls', () => {
    it('should render Reset button', () => {
      const resetButton = wrapper.findAll('.view-button').find(
        btn => btn.text().includes('Reset')
      )
      expect(resetButton?.exists()).toBe(true)
    })

    it('should render Fit button with icon', () => {
      const fitButton = wrapper.findAll('.view-button').find(
        btn => btn.classes().includes('icon-button')
      )
      expect(fitButton?.exists()).toBe(true)
      expect(fitButton?.find('svg').exists()).toBe(true)
    })

    it('should emit reset-view when clicking Reset button', async () => {
      const resetButton = wrapper.findAll('.view-button').find(
        btn => btn.text().includes('Reset')
      )
      await resetButton?.trigger('click')
      expect(wrapper.emitted('reset-view')).toBeTruthy()
    })

    it('should emit fit-to-screen when clicking Fit button', async () => {
      const fitButton = wrapper.findAll('.view-button').find(
        btn => btn.classes().includes('icon-button')
      )
      await fitButton?.trigger('click')
      expect(wrapper.emitted('fit-to-screen')).toBeTruthy()
    })
  })

  describe('accessibility', () => {
    it('should have title attributes on buttons', () => {
      const buttons = wrapper.findAll('button')
      buttons.forEach(button => {
        expect(button.attributes('title')).toBeDefined()
      })
    })

    it('should have group labels for screen readers', () => {
      const labels = wrapper.findAll('.group-label')
      expect(labels.length).toBeGreaterThan(0)
    })
  })

  describe('styling', () => {
    it('should apply glass morphism styling', () => {
      const toolbar = wrapper.find('.graph-toolbar')
      expect(toolbar.classes()).toContain('graph-toolbar')
    })

    it('should apply active state styling to active buttons', async () => {
      await wrapper.setProps({ currentLayout: LAYOUT_TYPES.FORCE })
      const forceButton = wrapper.findAll('.layout-button').find(
        btn => btn.text().includes('Force')
      )
      expect(forceButton?.classes()).toContain('active')
    })
  })
})
