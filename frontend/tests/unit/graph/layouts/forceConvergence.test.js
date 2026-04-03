import { describe, it, expect } from 'vitest'
import { runForceLayout } from '@/utils/graph/layouts/force.js'

function makeGraph(nodeCount) {
  const nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: `n${i}`,
    type: i % 3 === 0 ? 'Person' : i % 3 === 1 ? 'Concept' : 'Topic',
    x: Math.random() * 800,
    y: Math.random() * 600,
  }))
  const edges = []
  for (let i = 1; i < nodeCount; i++) {
    edges.push({ source: `n${Math.floor(Math.random() * i)}`, target: `n${i}`, weight: 1 })
  }
  return { nodes, edges }
}

describe('force layout with adaptive convergence', () => {
  it('small graph (10 nodes) produces valid positions', () => {
    const { nodes, edges } = makeGraph(10)
    runForceLayout(nodes, edges, { width: 800, height: 600 })
    nodes.forEach(n => {
      expect(Number.isFinite(n.x)).toBe(true)
      expect(Number.isFinite(n.y)).toBe(true)
    })
  })

  it('large graph (200 nodes) produces well-separated layout', () => {
    const { nodes, edges } = makeGraph(200)
    runForceLayout(nodes, edges, { width: 800, height: 600 })
    const xs = nodes.map(n => n.x)
    const ys = nodes.map(n => n.y)
    const xRange = Math.max(...xs) - Math.min(...xs)
    const yRange = Math.max(...ys) - Math.min(...ys)
    expect(xRange).toBeGreaterThan(200)
    expect(yRange).toBeGreaterThan(200)
  })

  it('backward compat: convergence false runs fixed iterations', () => {
    const { nodes, edges } = makeGraph(10)
    const sim = runForceLayout(nodes, edges, {
      width: 800, height: 600,
      convergence: false,
      iterations: 50,
    })
    expect(sim.alpha()).toBeGreaterThan(0)
  })

  it('live mode: iterations=0 with convergence=false leaves sim running', () => {
    const { nodes, edges } = makeGraph(10)
    const sim = runForceLayout(nodes, edges, {
      width: 800, height: 600,
      convergence: false,
      iterations: 0,
    })
    expect(sim.alpha()).toBeGreaterThan(0)
  })

  it('live mode preserved when convergence=true but iterations=0', () => {
    const { nodes, edges } = makeGraph(10)
    const sim = runForceLayout(nodes, edges, {
      width: 800, height: 600,
      convergence: true,
      iterations: 0,
    })
    expect(sim.alpha()).toBeGreaterThan(0)
  })

  it('empty graph returns immediately', () => {
    const sim = runForceLayout([], [], { width: 800, height: 600 })
    expect(sim).toBeDefined()
  })

  it('single node converges instantly', () => {
    const nodes = [{ id: 'n0', type: 'Person', x: 400, y: 300 }]
    runForceLayout(nodes, [], { width: 800, height: 600 })
    expect(Number.isFinite(nodes[0].x)).toBe(true)
  })

  it('dense graph completes without infinite loop (maxIterations cap)', () => {
    const nodes = Array.from({ length: 20 }, (_, i) => ({
      id: `n${i}`, type: 'Person', x: 400, y: 300,
    }))
    const edges = []
    for (let i = 0; i < 10; i++) {
      for (let j = i + 1; j < 10; j++) {
        edges.push({ source: `n${i}`, target: `n${j}`, weight: 1 })
      }
    }
    const sim = runForceLayout(nodes, edges, { width: 800, height: 600 })
    expect(sim).toBeDefined()
    nodes.forEach(n => expect(Number.isFinite(n.x)).toBe(true))
  })
})
