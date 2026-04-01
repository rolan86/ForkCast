import { describe, it, expect } from 'vitest'
import {
  VISUAL_MODES,
  RENDER_CONFIG_3D,
  CONNECTION_STYLES,
  PERFORMANCE_PRESETS,
} from '@/constants/graph.js'

describe('3D graph constants', () => {
  it('VISUAL_MODES includes 3d', () => {
    expect(VISUAL_MODES.THREE_D).toBe('3d')
    expect(VISUAL_MODES.TWO_D).toBe('2d')
    expect(VISUAL_MODES.TWO_POINT_FIVE_D).toBe('2.5d')
  })

  it('RENDER_CONFIG_3D has required camera defaults', () => {
    expect(RENDER_CONFIG_3D).toMatchObject({
      cameraFOV: expect.any(Number),
      cameraDistance: expect.any(Number),
      maxCameraDistance: expect.any(Number),
      minCameraDistance: expect.any(Number),
      orbitDamping: expect.any(Number),
    })
    expect(RENDER_CONFIG_3D.cameraFOV).toBe(60)
  })

  it('CONNECTION_STYLES defines three styles', () => {
    expect(CONNECTION_STYLES.CURVED).toBe('curved')
    expect(CONNECTION_STYLES.PARTICLE).toBe('particle')
    expect(CONNECTION_STYLES.ADAPTIVE).toBe('adaptive')
  })

  it('PERFORMANCE_PRESETS defines three presets with expected shapes', () => {
    expect(PERFORMANCE_PRESETS.QUALITY).toMatchObject({
      glow: true,
      pulse: true,
      connectionStyle: 'curved',
    })
    expect(PERFORMANCE_PRESETS.BALANCED).toMatchObject({
      glow: true,
      pulse: false,
      connectionStyle: 'adaptive',
    })
    expect(PERFORMANCE_PRESETS.PERFORMANCE).toMatchObject({
      glow: false,
      pulse: false,
      connectionStyle: 'curved',
    })
  })
})
