import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphSettingsPanel from '@/components/graph/GraphSettingsPanel.vue'

describe('GraphSettingsPanel — 3D section', () => {
  const baseProps = {
    isOpen: true,
    currentLayout: 'force',
    visualMode: '3d',
    performanceMode: false,
    renderMode: 'hybrid',
  }

  it('shows 3D settings section when visualMode is 3d', () => {
    const wrapper = mount(GraphSettingsPanel, { props: baseProps })
    expect(wrapper.text()).toContain('3D Settings')
    expect(wrapper.text()).toContain('Connection Style')
  })

  it('hides 3D settings section when visualMode is 2d', () => {
    const wrapper = mount(GraphSettingsPanel, {
      props: { ...baseProps, visualMode: '2d' },
    })
    expect(wrapper.text()).not.toContain('3D Settings')
  })

  it('emits update-3d-settings when connection style changes', async () => {
    const wrapper = mount(GraphSettingsPanel, { props: baseProps })
    const select = wrapper.find('[data-testid="connection-style-select"]')
    await select.setValue('particle')
    expect(wrapper.emitted('update-3d-settings')).toBeTruthy()
    expect(wrapper.emitted('update-3d-settings')[0][0]).toMatchObject({
      connectionStyle: 'particle',
    })
  })

  it('emits apply-performance-preset when preset button clicked', async () => {
    const wrapper = mount(GraphSettingsPanel, { props: baseProps })
    const btn = wrapper.find('[data-testid="preset-balanced"]')
    await btn.trigger('click')
    expect(wrapper.emitted('apply-performance-preset')).toBeTruthy()
    expect(wrapper.emitted('apply-performance-preset')[0][0]).toBe('balanced')
  })
})
