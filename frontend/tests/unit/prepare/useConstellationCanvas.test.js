import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useConstellationCanvas } from '@/composables/useConstellationCanvas.js'

// Mock canvas context
function createMockCanvas() {
  const ctx = {
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    closePath: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    fillRect: vi.fn(),
    canvas: { width: 800, height: 400 },
    fillStyle: '',
    strokeStyle: '',
    globalAlpha: 1,
    lineWidth: 1,
    shadowBlur: 0,
    shadowColor: '',
    scale: vi.fn(),
    createRadialGradient: vi.fn(() => ({
      addColorStop: vi.fn(),
    })),
  }
  const canvas = {
    getContext: vi.fn(() => ctx),
    width: 800,
    height: 400,
    getBoundingClientRect: vi.fn(() => ({ width: 800, height: 400 })),
  }
  return { canvas, ctx }
}

describe('useConstellationCanvas', () => {
  let mockRaf
  beforeEach(() => {
    mockRaf = vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation(cb => {
      setTimeout(cb, 0)
      return 1
    })
    vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes with empty node and edge arrays', () => {
    const constellation = useConstellationCanvas()
    expect(constellation.nodes.value).toEqual([])
    expect(constellation.edges.value).toEqual([])
  })

  it('adds seed nodes with specified color', () => {
    const constellation = useConstellationCanvas()
    const { canvas } = createMockCanvas()
    constellation.init(canvas)

    constellation.addSeedNode('#00d4ff')
    expect(constellation.nodes.value).toHaveLength(1)
    expect(constellation.nodes.value[0].color).toBe('#00d4ff')
    expect(constellation.nodes.value[0].type).toBe('seed')

    constellation.destroy()
  })

  it('adds agent nodes with accent color and pulse', () => {
    const constellation = useConstellationCanvas()
    const { canvas } = createMockCanvas()
    constellation.init(canvas)

    constellation.addAgentNode('agent_1')
    expect(constellation.nodes.value).toHaveLength(1)
    expect(constellation.nodes.value[0].type).toBe('agent')
    expect(constellation.nodes.value[0].id).toBe('agent_1')
    expect(constellation.nodes.value[0].pulseAlpha).toBeGreaterThan(0)

    constellation.destroy()
  })

  it('creates edges between nearby nodes', () => {
    const constellation = useConstellationCanvas()
    const { canvas } = createMockCanvas()
    constellation.init(canvas)

    // Add nodes close together
    constellation.addSeedNode('#00d4ff')
    constellation.addSeedNode('#818cf8')
    // Edges form between nearby nodes
    expect(constellation.edges.value.length).toBeGreaterThanOrEqual(1)

    constellation.destroy()
  })

  it('computes morph target positions for a 3-column grid', () => {
    const constellation = useConstellationCanvas()
    const { canvas } = createMockCanvas()
    constellation.init(canvas)

    for (let i = 0; i < 6; i++) {
      constellation.addAgentNode(`agent_${i}`)
    }

    const targets = constellation.computeGridTargets(800, 400, 6)
    expect(targets).toHaveLength(6)
    // First row: 3 items
    expect(targets[0].col).toBe(0)
    expect(targets[1].col).toBe(1)
    expect(targets[2].col).toBe(2)
    // Second row
    expect(targets[3].col).toBe(0)
    expect(targets[3].row).toBe(1)

    constellation.destroy()
  })

  it('cleans up animation frame on destroy', () => {
    const constellation = useConstellationCanvas()
    const { canvas } = createMockCanvas()
    constellation.init(canvas)

    const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame')
    constellation.destroy()
    expect(cancelSpy).toHaveBeenCalled()
  })
})
