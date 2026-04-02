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
    it('returns segments and jitter for lightning generation', () => {
      const cfg = getNeuronConfig(0.5)
      expect(cfg.segments).toBeGreaterThan(10)
      expect(cfg.jitter).toBeGreaterThan(0)
    })

    it('more segments for higher weight', () => {
      const weak = getNeuronConfig(0.1)
      const strong = getNeuronConfig(1.0)
      expect(strong.segments).toBeGreaterThan(weak.segments)
    })

    it('returns glow opacity and restrike interval', () => {
      const cfg = getNeuronConfig(0.5)
      expect(cfg.glowOpacity).toBeGreaterThan(0)
      expect(cfg.glowOpacity).toBeLessThanOrEqual(1)
      expect(cfg.restrikeInterval).toBeGreaterThan(0)
    })
  })

  describe('generateLightningPath', () => {
    const start = { x: 0, y: 0, z: 0 }
    const end = { x: 10, y: 0, z: 0 }

    it('returns start and end points with intermediate segments', () => {
      const points = generateLightningPath(start, end, 5, 1.0)
      expect(points.length).toBe(7) // start + 5 segments + end
      expect(points[0]).toEqual(start)
      expect(points[6]).toEqual(end)
    })

    it('intermediate points are displaced from the straight line', () => {
      // Use deterministic rng that always returns 0.9 (off-center)
      const rng = () => 0.9
      const points = generateLightningPath(start, end, 5, 3.0, rng)

      // At least one intermediate point should be displaced in y or z
      const intermediates = points.slice(1, -1)
      const hasDisplacement = intermediates.some(
        p => Math.abs(p.y) > 0.1 || Math.abs(p.z) > 0.1,
      )
      expect(hasDisplacement).toBe(true)
    })

    it('jitter is tapered toward endpoints (envelope)', () => {
      // Use fixed rng to isolate envelope effect
      const rng = () => 1.0 // max displacement
      const points = generateLightningPath(start, end, 10, 5.0, rng)

      // Middle point should have more displacement than points near edges
      const mid = points[6] // ~middle
      const nearStart = points[1] // near start
      const midDisp = Math.sqrt(mid.y * mid.y + mid.z * mid.z)
      const nearDisp = Math.sqrt(nearStart.y * nearStart.y + nearStart.z * nearStart.z)
      expect(midDisp).toBeGreaterThan(nearDisp)
    })

    it('handles zero-length edges gracefully', () => {
      const same = { x: 5, y: 5, z: 5 }
      const points = generateLightningPath(same, same, 5, 2.0)
      expect(points.length).toBe(2) // just start and end
    })

    it('works in 3D (not just along x-axis)', () => {
      const s = { x: 0, y: 0, z: 0 }
      const e = { x: 5, y: 5, z: 5 }
      const points = generateLightningPath(s, e, 8, 2.0)
      expect(points.length).toBe(10)
      expect(points[0]).toEqual(s)
      expect(points[9]).toEqual(e)
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
