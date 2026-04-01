import { describe, it, expect } from 'vitest'
import {
  screenToNDC,
  isPointInPolygon,
  projectToScreen,
  computeDiveInTarget,
  computePathHighlightSet,
} from '@/utils/graph/interactions/modes3d.js'

describe('modes3d', () => {
  describe('screenToNDC', () => {
    it('converts center of screen to (0, 0)', () => {
      const ndc = screenToNDC(400, 300, 800, 600)
      expect(ndc.x).toBeCloseTo(0)
      expect(ndc.y).toBeCloseTo(0)
    })

    it('converts top-left to (-1, 1)', () => {
      const ndc = screenToNDC(0, 0, 800, 600)
      expect(ndc.x).toBeCloseTo(-1)
      expect(ndc.y).toBeCloseTo(1)
    })

    it('converts bottom-right to (1, -1)', () => {
      const ndc = screenToNDC(800, 600, 800, 600)
      expect(ndc.x).toBeCloseTo(1)
      expect(ndc.y).toBeCloseTo(-1)
    })
  })

  describe('isPointInPolygon', () => {
    const square = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ]

    it('returns true for point inside', () => {
      expect(isPointInPolygon({ x: 5, y: 5 }, square)).toBe(true)
    })

    it('returns false for point outside', () => {
      expect(isPointInPolygon({ x: 15, y: 5 }, square)).toBe(false)
    })

    it('handles triangle polygon', () => {
      const triangle = [
        { x: 0, y: 0 },
        { x: 10, y: 0 },
        { x: 5, y: 10 },
      ]
      expect(isPointInPolygon({ x: 5, y: 3 }, triangle)).toBe(true)
      expect(isPointInPolygon({ x: 0, y: 10 }, triangle)).toBe(false)
    })
  })

  describe('computeDiveInTarget', () => {
    it('returns camera position at diveInDistance from node', () => {
      const node = { x: 100, y: 0, z: 0 }
      const cameraPos = { x: 0, y: 0, z: 150 }
      const target = computeDiveInTarget(node, cameraPos, 30)

      const dx = target.x - node.x
      const dy = target.y - node.y
      const dz = target.z - node.z
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz)
      expect(dist).toBeCloseTo(30, 0)
    })

    it('positions camera between current position and node', () => {
      const node = { x: 0, y: 0, z: 0 }
      const cameraPos = { x: 0, y: 0, z: 150 }
      const target = computeDiveInTarget(node, cameraPos, 30)
      expect(target.z).toBeGreaterThan(node.z)
      expect(target.z).toBeLessThan(cameraPos.z)
    })
  })

  describe('projectToScreen', () => {
    it('converts NDC center (0,0) to screen center', () => {
      const screen = projectToScreen({ x: 0, y: 0 }, null, 800, 600)
      expect(screen.x).toBeCloseTo(400)
      expect(screen.y).toBeCloseTo(300)
    })

    it('converts NDC (-1, 1) to top-left', () => {
      const screen = projectToScreen({ x: -1, y: 1 }, null, 800, 600)
      expect(screen.x).toBeCloseTo(0)
      expect(screen.y).toBeCloseTo(0)
    })

    it('converts NDC (1, -1) to bottom-right', () => {
      const screen = projectToScreen({ x: 1, y: -1 }, null, 800, 600)
      expect(screen.x).toBeCloseTo(800)
      expect(screen.y).toBeCloseTo(600)
    })
  })

  describe('computePathHighlightSet', () => {
    it('returns set of node IDs and edge keys on the path', () => {
      const path = ['a', 'b', 'c']
      const result = computePathHighlightSet(path)
      expect(result.nodeIds).toEqual(new Set(['a', 'b', 'c']))
      expect(result.edgeKeys).toEqual(new Set(['a->b', 'b->c']))
    })

    it('returns empty sets for empty path', () => {
      const result = computePathHighlightSet([])
      expect(result.nodeIds.size).toBe(0)
      expect(result.edgeKeys.size).toBe(0)
    })
  })
})
