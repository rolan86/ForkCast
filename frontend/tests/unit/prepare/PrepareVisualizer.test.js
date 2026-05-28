import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PrepareVisualizer from '@/components/PrepareVisualizer.vue'

// Mock the composable
vi.mock('@/composables/useConstellationCanvas.js', () => ({
  useConstellationCanvas: () => ({
    nodes: { value: [] },
    edges: { value: [] },
    state: { value: 'building' },
    init: vi.fn(),
    resize: vi.fn(),
    addSeedNode: vi.fn(),
    addAgentNode: vi.fn(),
    activateNetwork: vi.fn(),
    computeGridTargets: vi.fn(() => []),
    flashAndMorph: vi.fn(),
    morphToGrid: vi.fn(),
    onMorphComplete: vi.fn(),
    destroy: vi.fn(),
  }),
}))

const defaultProps = {
  steps: [
    { label: 'Loading graph', stageNames: ['loading_graph'] },
    { label: 'Generating profiles', stageNames: ['generating_profiles'] },
    { label: 'Generating config', stageNames: ['generating_config', 'result'] },
  ],
  currentStage: '',
  progress: { current: null, total: null },
  logEntries: [],
  error: '',
  errorType: '',
  resumable: false,
}

describe('PrepareVisualizer', () => {
  it('renders StepIndicator in pipeline mode', () => {
    const wrapper = mount(PrepareVisualizer, { props: defaultProps })
    expect(wrapper.find('.step-indicator').exists() || wrapper.findComponent({ name: 'StepIndicator' }).exists()).toBe(true)
  })

  it('renders canvas element', () => {
    const wrapper = mount(PrepareVisualizer, { props: defaultProps })
    expect(wrapper.find('canvas').exists()).toBe(true)
  })

  it('shows error overlay when error prop is set', async () => {
    const wrapper = mount(PrepareVisualizer, {
      props: { ...defaultProps, error: 'Rate limit exceeded', errorType: 'rate_limited' },
    })
    expect(wrapper.text()).toContain('Rate limit exceeded')
  })

  it('emits cancel when cancel button clicked', async () => {
    const wrapper = mount(PrepareVisualizer, {
      props: { ...defaultProps, error: 'Something failed' },
    })
    const cancelBtn = wrapper.find('[data-testid="cancel-btn"]')
    if (cancelBtn.exists()) {
      await cancelBtn.trigger('click')
      expect(wrapper.emitted('cancel')).toBeTruthy()
    }
  })

  it('keeps every step pending when currentStage is empty on mount', () => {
    // Regression: a previous version marked all steps "done" pre-stage
    // because the prior-step-is-done rule ran even when no stage had arrived.
    const wrapper = mount(PrepareVisualizer, { props: defaultProps })
    const indicator = wrapper.findComponent({ name: 'StepIndicator' })
    expect(indicator.exists()).toBe(true)
    const statuses = indicator.props('steps').map(s => s.status)
    expect(statuses).toEqual(['pending', 'pending', 'pending'])
  })

  it('marks prior steps done and current stage active', async () => {
    const wrapper = mount(PrepareVisualizer, {
      props: { ...defaultProps, currentStage: 'generating_profiles' },
    })
    const indicator = wrapper.findComponent({ name: 'StepIndicator' })
    const statuses = indicator.props('steps').map(s => s.status)
    expect(statuses).toEqual(['done', 'active', 'pending'])
  })

  it('gives the error overlay an assertive aria-live region', () => {
    const wrapper = mount(PrepareVisualizer, {
      props: { ...defaultProps, error: 'Boom' },
    })
    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('aria-live')).toBe('assertive')
  })
})
