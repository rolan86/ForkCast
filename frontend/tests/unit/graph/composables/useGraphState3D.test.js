import { describe, it, expect, beforeEach } from 'vitest'
import { useGraphState } from '@/composables/useGraphState.js'
import { CONNECTION_STYLES, PERFORMANCE_PRESETS } from '@/constants/graph.js'

describe('useGraphState — 3D extensions', () => {
  let graphState, update3DSettings, applyPerformancePreset

  beforeEach(() => {
    const gs = useGraphState()
    graphState = gs.graphState
    update3DSettings = gs.update3DSettings
    applyPerformancePreset = gs.applyPerformancePreset
  })

  it('includes 3D-specific state with defaults', () => {
    expect(graphState.settings3d).toMatchObject({
      connectionStyle: CONNECTION_STYLES.CURVED,
      glowEnabled: true,
      pulseEnabled: true,
      autoRotate: false,
      performancePreset: 'quality',
    })
  })

  it('update3DSettings merges partial updates', () => {
    update3DSettings({ connectionStyle: CONNECTION_STYLES.PARTICLE })
    expect(graphState.settings3d.connectionStyle).toBe('particle')
    expect(graphState.settings3d.glowEnabled).toBe(true) // unchanged
  })

  it('applyPerformancePreset sets all fields from preset', () => {
    applyPerformancePreset('balanced')
    expect(graphState.settings3d.glowEnabled).toBe(true)
    expect(graphState.settings3d.pulseEnabled).toBe(false)
    expect(graphState.settings3d.connectionStyle).toBe('adaptive')
    expect(graphState.settings3d.performancePreset).toBe('balanced')
  })

  it('applyPerformancePreset handles performance preset', () => {
    applyPerformancePreset('performance')
    expect(graphState.settings3d.glowEnabled).toBe(false)
    expect(graphState.settings3d.pulseEnabled).toBe(false)
    expect(graphState.settings3d.performancePreset).toBe('performance')
  })

  it('3D state persists to localStorage alongside layout params', () => {
    update3DSettings({ autoRotate: true })
    expect(graphState.settings3d.autoRotate).toBe(true)
  })
})
