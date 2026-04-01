import { describe, it, expect } from 'vitest'
import {
  createNodeMaterial,
  createGlowMaterial,
  getPulseScale,
  getNodeRadius,
  getGeometryType,
} from '@/utils/graph/rendering/neuralEffects.js'
import { RENDER_CONFIG_3D } from '@/constants/graph.js'

describe('neuralEffects', () => {
  describe('getNodeRadius', () => {
    it('returns base radius for zero connections', () => {
      expect(getNodeRadius(0)).toBe(RENDER_CONFIG_3D.nodeBaseRadius)
    })

    it('scales with connection count up to max', () => {
      const r5 = getNodeRadius(5)
      const r20 = getNodeRadius(20)
      expect(r5).toBeGreaterThan(RENDER_CONFIG_3D.nodeBaseRadius)
      expect(r20).toBeGreaterThan(r5)
      expect(r20).toBeLessThanOrEqual(RENDER_CONFIG_3D.nodeMaxRadius)
    })

    it('clamps at max radius', () => {
      expect(getNodeRadius(1000)).toBe(RENDER_CONFIG_3D.nodeMaxRadius)
    })
  })

  describe('getPulseScale', () => {
    it('returns 1.0 at time 0', () => {
      expect(getPulseScale(0)).toBeCloseTo(1.0, 2)
    })

    it('oscillates within amplitude bounds', () => {
      const amp = RENDER_CONFIG_3D.pulseAmplitude
      for (let t = 0; t < 5000; t += 100) {
        const scale = getPulseScale(t)
        expect(scale).toBeGreaterThanOrEqual(1 - amp - 0.001)
        expect(scale).toBeLessThanOrEqual(1 + amp + 0.001)
      }
    })
  })

  describe('getGeometryType', () => {
    it('returns sphere for small graphs', () => {
      expect(getGeometryType(100)).toBe('sphere')
    })

    it('returns icosahedron for large graphs', () => {
      expect(getGeometryType(500)).toBe('icosahedron')
    })

    it('uses sphereNodeThreshold as boundary', () => {
      expect(getGeometryType(RENDER_CONFIG_3D.sphereNodeThreshold - 1)).toBe('sphere')
      expect(getGeometryType(RENDER_CONFIG_3D.sphereNodeThreshold)).toBe('icosahedron')
    })
  })

  describe('createNodeMaterial', () => {
    it('returns object with required Three.js material properties', () => {
      const mat = createNodeMaterial('#ff0000', { glow: true })
      expect(mat).toMatchObject({
        color: '#ff0000',
        emissive: '#ff0000',
        emissiveIntensity: expect.any(Number),
        transparent: true,
      })
    })

    it('sets lower emissive when glow disabled', () => {
      const withGlow = createNodeMaterial('#ff0000', { glow: true })
      const noGlow = createNodeMaterial('#ff0000', { glow: false })
      expect(noGlow.emissiveIntensity).toBeLessThan(withGlow.emissiveIntensity)
    })
  })

  describe('createGlowMaterial', () => {
    it('returns transparent backside material', () => {
      const mat = createGlowMaterial('#00ff00')
      expect(mat).toMatchObject({
        color: '#00ff00',
        transparent: true,
        opacity: expect.any(Number),
        side: 'back',
      })
      expect(mat.opacity).toBeLessThan(0.5)
    })
  })
})
