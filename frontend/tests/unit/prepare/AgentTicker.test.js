import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentTicker from '@/components/AgentTicker.vue'

describe('AgentTicker', () => {
  it('renders nothing when queue is empty', () => {
    const wrapper = mount(AgentTicker)
    expect(wrapper.find('.agent-ticker__entry').exists()).toBe(false)
  })

  it('displays agent name and bio when pushed', async () => {
    const wrapper = mount(AgentTicker)
    await wrapper.vm.push({ name: '@techskeptic', bio: 'AI safety researcher' })
    await wrapper.vm.$nextTick()

    const entry = wrapper.find('.agent-ticker__entry')
    expect(entry.exists()).toBe(true)
    expect(entry.text()).toContain('@techskeptic')
    expect(entry.text()).toContain('AI safety researcher')
  })

  it('falls back to stage text when no agent data', async () => {
    const wrapper = mount(AgentTicker, {
      props: { fallbackText: 'Generating profiles (3/15)' },
    })
    // No push() call — should show fallback
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Generating profiles (3/15)')
  })

  it('queues multiple entries and shows them sequentially', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AgentTicker)
    await wrapper.vm.push({ name: '@agent1', bio: 'First agent' })
    await wrapper.vm.push({ name: '@agent2', bio: 'Second agent' })
    await wrapper.vm.$nextTick()

    // First entry visible immediately
    expect(wrapper.text()).toContain('@agent1')

    // Advance past display duration
    vi.advanceTimersByTime(2500)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('@agent2')

    vi.useRealTimers()
  })
})
