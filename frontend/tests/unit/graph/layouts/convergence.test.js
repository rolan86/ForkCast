import { describe, it, expect } from 'vitest'
import {
  computeKineticEnergy,
  hasConverged,
  adaptAlphaDecay,
} from '@/utils/graph/layouts/convergence.js'

describe('computeKineticEnergy', () => {
  it('returns per-node energy for known velocities', () => {
    const nodes = [
      { vx: 3, vy: 4 },   // 9 + 16 = 25
      { vx: 0, vy: 5 },   // 0 + 25 = 25
    ]
    expect(computeKineticEnergy(nodes)).toBe(25)
  })

  it('returns 0 for all-zero velocities', () => {
    const nodes = [
      { vx: 0, vy: 0 },
      { vx: 0, vy: 0 },
    ]
    expect(computeKineticEnergy(nodes)).toBe(0)
  })

  it('handles single node', () => {
    const nodes = [{ vx: 1, vy: 1 }]
    expect(computeKineticEnergy(nodes)).toBe(2)
  })

  it('returns 0 for empty array (no division by zero)', () => {
    expect(computeKineticEnergy([])).toBe(0)
  })

  it('normalizes: same per-node velocity gives same energy regardless of count', () => {
    const makeNodes = (n) => Array.from({ length: n }, () => ({ vx: 1, vy: 1 }))
    expect(computeKineticEnergy(makeNodes(10))).toBe(computeKineticEnergy(makeNodes(100)))
  })

  it('treats missing vx/vy as 0', () => {
    const nodes = [{ vx: 3 }, { vy: 4 }, {}]
    expect(computeKineticEnergy(nodes)).toBeCloseTo(25 / 3)
  })
})

describe('hasConverged', () => {
  it('returns true when energy is below threshold', () => {
    expect(hasConverged(0.3, 0.5, 10, 800)).toBe(true)
  })

  it('returns false when energy is above threshold and below max', () => {
    expect(hasConverged(1.0, 0.5, 10, 800)).toBe(false)
  })

  it('returns true when iteration reaches max (inclusive)', () => {
    expect(hasConverged(999, 0.5, 799, 799)).toBe(true)
  })

  it('returns true for zero energy', () => {
    expect(hasConverged(0, 0.5, 0, 800)).toBe(true)
  })
})

describe('adaptAlphaDecay', () => {
  const bounds = { min: 0.005, max: 0.05, adaptRate: 0.2 }

  it('increases decay when energy is decreasing (positive delta)', () => {
    const result = adaptAlphaDecay(0.02, 0.1, bounds)
    expect(result).toBeGreaterThan(0.02)
  })

  it('decreases decay when energy is increasing (negative delta, oscillation)', () => {
    const result = adaptAlphaDecay(0.02, -0.1, bounds)
    expect(result).toBeLessThan(0.02)
  })

  it('increases decay when near equilibrium (tiny delta)', () => {
    const result = adaptAlphaDecay(0.02, 0.0005, bounds)
    expect(result).toBeGreaterThan(0.02)
  })

  it('clamps to minimum bound', () => {
    const result = adaptAlphaDecay(0.006, -0.5, bounds)
    expect(result).toBeGreaterThanOrEqual(bounds.min)
  })

  it('clamps to maximum bound', () => {
    const result = adaptAlphaDecay(0.045, 0.5, bounds)
    expect(result).toBeLessThanOrEqual(bounds.max)
  })
})
