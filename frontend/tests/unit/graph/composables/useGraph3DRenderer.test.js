import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock three before importing
vi.mock('three', () => {
  function SphereGeometry() {}
  function IcosahedronGeometry() {}
  function MeshStandardMaterial() {}
  function MeshBasicMaterial() {}
  function Color(c) { this.value = c }
  function Mesh() { this.add = vi.fn(); this.scale = { setScalar: vi.fn() }; this.material = {} }
  function Group() { this.add = vi.fn(); this.scale = { setScalar: vi.fn() } }
  function Sprite() { this.position = { set: vi.fn() }; this.scale = { set: vi.fn() } }
  function SpriteMaterial() {}
  function CanvasTexture() { this.needsUpdate = false }
  function AmbientLight() {}
  function PointLight() { this.position = { set: vi.fn() } }
  function Vector3() { this.project = vi.fn().mockReturnThis() }
  return {
    SphereGeometry: vi.fn().mockImplementation(function (...args) { return new SphereGeometry(...args) }),
    IcosahedronGeometry: vi.fn().mockImplementation(function (...args) { return new IcosahedronGeometry(...args) }),
    MeshStandardMaterial: vi.fn().mockImplementation(function (...args) { return new MeshStandardMaterial(...args) }),
    MeshBasicMaterial: vi.fn().mockImplementation(function (...args) { return new MeshBasicMaterial(...args) }),
    Color: vi.fn().mockImplementation(function (c) { return new Color(c) }),
    Mesh: vi.fn().mockImplementation(function (...args) { return new Mesh(...args) }),
    Group: vi.fn().mockImplementation(function (...args) { return new Group(...args) }),
    Sprite: vi.fn().mockImplementation(function (...args) { return new Sprite(...args) }),
    SpriteMaterial: vi.fn().mockImplementation(function (...args) { return new SpriteMaterial(...args) }),
    CanvasTexture: vi.fn().mockImplementation(function (...args) { return new CanvasTexture(...args) }),
    AmbientLight: vi.fn().mockImplementation(function (...args) { return new AmbientLight(...args) }),
    PointLight: vi.fn().mockImplementation(function (...args) { return new PointLight(...args) }),
    BackSide: 1,
    Vector3: vi.fn().mockImplementation(function (...args) { return new Vector3(...args) }),
  }
})

// Mock d3-force-3d
vi.mock('d3-force-3d', () => ({
  forceManyBody: vi.fn(() => ({
    strength: vi.fn().mockReturnThis(),
  })),
}))

// Mock 3d-force-graph before importing
vi.mock('3d-force-graph', () => {
  const mockInstance = {
    graphData: vi.fn(function (data) {
      if (data !== undefined) {
        mockInstance._data = data
        return mockInstance
      }
      return mockInstance._data || { nodes: [], links: [] }
    }),
    nodeThreeObject: vi.fn().mockReturnThis(),
    nodeThreeObjectExtend: vi.fn().mockReturnThis(),
    nodeLabel: vi.fn().mockReturnThis(),
    linkCurvature: vi.fn().mockReturnThis(),
    linkDirectionalParticles: vi.fn().mockReturnThis(),
    linkDirectionalParticleSpeed: vi.fn().mockReturnThis(),
    linkWidth: vi.fn().mockReturnThis(),
    linkOpacity: vi.fn().mockReturnThis(),
    backgroundColor: vi.fn().mockReturnThis(),
    width: vi.fn().mockReturnThis(),
    height: vi.fn().mockReturnThis(),
    d3Force: vi.fn().mockReturnThis(),
    d3AlphaDecay: vi.fn().mockReturnThis(),
    onNodeClick: vi.fn().mockReturnThis(),
    onNodeHover: vi.fn().mockReturnThis(),
    onBackgroundClick: vi.fn().mockReturnThis(),
    controls: vi.fn().mockReturnValue({
      autoRotate: false,
      autoRotateSpeed: 0.5,
      enableDamping: true,
      dampingFactor: 0.05,
    }),
    camera: vi.fn().mockReturnValue({
      position: { x: 0, y: 0, z: 150, set: vi.fn(), distanceTo: vi.fn(() => 150) },
    }),
    cameraPosition: vi.fn(),
    scene: vi.fn().mockReturnValue({ add: vi.fn() }),
    renderer: vi.fn().mockReturnValue({ domElement: document.createElement('canvas') }),
    _destructor: vi.fn(),
  }
  return { default: vi.fn(() => vi.fn(() => mockInstance)) }
})

import { useGraph3DRenderer } from '@/composables/useGraph3DRenderer.js'

describe('useGraph3DRenderer', () => {
  let renderer

  beforeEach(() => {
    renderer = useGraph3DRenderer()
  })

  it('exports render, update, resize, destroy, getFps functions', () => {
    expect(typeof renderer.render).toBe('function')
    expect(typeof renderer.update).toBe('function')
    expect(typeof renderer.resize).toBe('function')
    expect(typeof renderer.destroy).toBe('function')
    expect(typeof renderer.getFps).toBe('function')
  })

  it('render initializes the force graph with data', async () => {
    const container = document.createElement('div')
    const graphData = {
      nodes: [{ id: 'a', type: 'Person' }, { id: 'b', type: 'Concept' }],
      edges: [{ source: 'a', target: 'b', weight: 1 }],
    }

    await renderer.render(container, graphData, 800, 600, {
      visualMode: '3d',
      connectionStyle: 'curved',
      glowEnabled: true,
      pulseEnabled: true,
    })

    // Should have initialized 3d-force-graph
    const ForceGraph3D = (await import('3d-force-graph')).default
    expect(ForceGraph3D).toHaveBeenCalled()
  })

  it('destroy cleans up resources', () => {
    const container = document.createElement('div')
    renderer.render(container, { nodes: [], edges: [] }, 800, 600, {})
    renderer.destroy()
    // Should not throw on double-destroy
    renderer.destroy()
  })
})
