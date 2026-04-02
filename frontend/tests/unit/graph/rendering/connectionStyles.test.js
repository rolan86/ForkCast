import { describe, it, expect } from 'vitest'
import {
  getCurvedConfig,
  getParticleConfig,
  getNeuronConfig,
  generateLightningPath,
  getAdaptiveStyle,
  getEdgeOpacity,
  getEdgeWidth,
} from '@/utils/graph/rendering/connectionStyles.js'
import { CONNECTION_STYLES, ADAPTIVE_THRESHOLDS } from '@/constants/graph.js'

describe('connectionStyles', () => {
  describe('getCurvedConfig', () => {
    it('returns curvature inversely proportional to weight', () => {
      const weak = getCurvedConfig(0.1)
      const strong = getCurvedConfig(1.0)
      expect(weak.curvature).toBeGreaterThan(strong.curvature)
    })

    it('returns shimmer opacity range', () => {
      const cfg = getCurvedConfig(0.5)
      expect(cfg.opacityRange).toEqual([0.3, 0.6])
    })
  })

  describe('getParticleConfig', () => {
    it('particle speed scales with edge weight', () => {
      const slow = getParticleConfig(0.2)
      const fast = getParticleConfig(1.0)
      expect(fast.speed).toBeGreaterThan(slow.speed)
    })

    it('returns emission rate within 1-3 range', () => {
      const cfg = getParticleConfig(0.5)
      expect(cfg.emissionRate).toBeGreaterThanOrEqual(1)
      expect(cfg.emissionRate).toBeLessThanOrEqual(3)
    })
  })

  describe('getNeuronConfig', () => {
    it('returns fractal subdivision parameters', () => {
      const cfg = getNeuronConfig(0.5)
      expect(cfg.generations).toBe(5)
      expect(cfg.displacement).toBeGreaterThan(0)
      expect(cfg.roughness).toBeGreaterThan(0)
      expect(cfg.roughness).toBeLessThan(1)
    })

    it('higher weight means less displacement (tighter bolts)', () => {
      const weak = getNeuronConfig(0.1)
      const strong = getNeuronConfig(1.0)
      expect(weak.displacement).toBeGreaterThan(strong.displacement)
    })

    it('returns glow opacity and restrike interval', () => {
      const cfg = getNeuronConfig(0.5)
      expect(cfg.glowOpacity).toBeGreaterThan(0)
      expect(cfg.glowOpacity).toBeLessThanOrEqual(1)
      expect(cfg.restrikeInterval).toBeGreaterThan(0)
    })

    it('faster restrike for higher weight (more active synapses)', () => {
      const weak = getNeuronConfig(0.1)
      const strong = getNeuronConfig(1.0)
      expect(strong.restrikeInterval).toBeLessThan(weak.restrikeInterval)
    })
  })

  describe('generateLightningPath (fractal midpoint displacement)', () => {
    const start = { x: 0, y: 0, z: 0 }
    const end = { x: 10, y: 0, z: 0 }

    it('returns 2^generations + 1 points', () => {
      const points = generateLightningPath(start, end, 3, 0.4, 0.55)
      // 3 generations: start with 2 points, each gen doubles segments
      // gen 0: 2→3, gen 1: 3→5, gen 2: 5→9 = 2^3 + 1 = 9
      expect(points.length).toBe(9)
    })

    it('first and last points match start and end', () => {
      const points = generateLightningPath(start, end, 5, 0.4, 0.55)
      expect(points[0]).toEqual(start)
      expect(points[points.length - 1]).toEqual(end)
    })

    it('intermediate points are displaced from straight line', () => {
      // Use deterministic rng that always returns 0.9 (off-center)
      const rng = () => 0.9
      const points = generateLightningPath(start, end, 4, 0.5, 0.55, rng)
      const intermediates = points.slice(1, -1)
      const hasDisplacement = intermediates.some(
        p => Math.abs(p.y) > 0.01 || Math.abs(p.z) > 0.01,
      )
      expect(hasDisplacement).toBe(true)
    })

    it('higher generations produce more points', () => {
      const few = generateLightningPath(start, end, 3, 0.4, 0.55)
      const many = generateLightningPath(start, end, 6, 0.4, 0.55)
      expect(many.length).toBeGreaterThan(few.length)
    })

    it('roughness < 1 means later generations have less displacement', () => {
      // Compare two runs with same seed: low roughness should be smoother
      let callCount = 0
      const deterministicRng = () => { callCount++; return 0.8 }

      const rough = generateLightningPath(start, end, 4, 0.5, 0.9, deterministicRng)
      callCount = 0
      const smooth = generateLightningPath(start, end, 4, 0.5, 0.3, deterministicRng)

      // With same rng, lower roughness should produce less total displacement
      const roughMaxDisp = Math.max(...rough.slice(1, -1).map(p => Math.abs(p.y) + Math.abs(p.z)))
      const smoothMaxDisp = Math.max(...smooth.slice(1, -1).map(p => Math.abs(p.y) + Math.abs(p.z)))
      expect(roughMaxDisp).toBeGreaterThan(smoothMaxDisp)
    })

    it('handles zero-length edges gracefully', () => {
      const same = { x: 5, y: 5, z: 5 }
      const points = generateLightningPath(same, same, 5, 0.4, 0.55)
      expect(points.length).toBe(2)
    })

    it('works in 3D (diagonal edges)', () => {
      const s = { x: 0, y: 0, z: 0 }
      const e = { x: 5, y: 5, z: 5 }
      const points = generateLightningPath(s, e, 4, 0.4, 0.55)
      expect(points.length).toBe(17) // 2^4 + 1
      expect(points[0]).toEqual(s)
      expect(points[16]).toEqual(e)
    })

    it('accepts custom rng for deterministic output', () => {
      let counter = 0
      const rng = () => { counter++; return 0.5 }
      const p1 = generateLightningPath(start, end, 3, 0.4, 0.55, rng)

      counter = 0
      const p2 = generateLightningPath(start, end, 3, 0.4, 0.55, rng)

      // Same rng sequence → same points
      expect(p1).toEqual(p2)
    })
  })

  describe('getAdaptiveStyle', () => {
    it('returns straight at overview distance', () => {
      const style = getAdaptiveStyle(ADAPTIVE_THRESHOLDS.overviewDistance + 100)
      expect(style).toBe('straight')
    })

    it('returns curved at mid-range', () => {
      const style = getAdaptiveStyle(ADAPTIVE_THRESHOLDS.midRangeDistance - 10)
      expect(style).toBe(CONNECTION_STYLES.CURVED)
    })

    it('returns particle at close-up', () => {
      const style = getAdaptiveStyle(ADAPTIVE_THRESHOLDS.closeUpDistance - 10)
      expect(style).toBe(CONNECTION_STYLES.PARTICLE)
    })

    it('returns curved between overview and close-up', () => {
      const style = getAdaptiveStyle(ADAPTIVE_THRESHOLDS.overviewDistance - 100)
      expect(style).toBe(CONNECTION_STYLES.CURVED)
    })
  })

  describe('getEdgeWidth', () => {
    it('scales with weight', () => {
      expect(getEdgeWidth(1.0)).toBeGreaterThan(getEdgeWidth(0.1))
    })

    it('has a minimum width', () => {
      expect(getEdgeWidth(0)).toBeGreaterThan(0)
    })
  })

  describe('getEdgeOpacity', () => {
    it('returns full opacity when highlighted', () => {
      expect(getEdgeOpacity({ highlighted: true })).toBe(1.0)
    })

    it('returns near-zero for filtered edges', () => {
      expect(getEdgeOpacity({ filtered: true })).toBeLessThanOrEqual(0.05)
    })

    it('returns default opacity normally', () => {
      const op = getEdgeOpacity({})
      expect(op).toBeGreaterThan(0.2)
      expect(op).toBeLessThan(0.8)
    })
  })
})
