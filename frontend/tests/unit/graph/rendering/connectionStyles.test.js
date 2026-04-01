import { describe, it, expect } from 'vitest'
import {
  getCurvedConfig,
  getParticleConfig,
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
