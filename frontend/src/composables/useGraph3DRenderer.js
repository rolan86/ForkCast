import { shallowRef } from 'vue'
import {
  RENDER_CONFIG_3D,
  CONNECTION_STYLES,
  NEON_COLORS,
} from '@/constants/graph.js'
import { getNodeRadius, getGeometryType, getPulseScale, createNodeMaterial } from '@/utils/graph/rendering/neuralEffects.js'
import { getCurvedConfig, getParticleConfig, getNeuronConfig, getAdaptiveStyle, getEdgeWidth, getEdgeOpacity } from '@/utils/graph/rendering/connectionStyles.js'
import { screenToNDC, isPointInPolygon, computeDiveInTarget, computePathHighlightSet } from '@/utils/graph/interactions/modes3d.js'

export function useGraph3DRenderer() {
  const _graph = shallowRef(null)
  const _container = shallowRef(null)
  const _animationFrame = shallowRef(null)
  const _fps = shallowRef(60)
  const _isDivedIn = shallowRef(false)

  let _frameCount = 0
  let _lastFpsTime = performance.now()

  function _trackFps() {
    _frameCount++
    const now = performance.now()
    if (now - _lastFpsTime >= 1000) {
      _fps.value = _frameCount
      _frameCount = 0
      _lastFpsTime = now
    }
  }

  async function render(container, graphData, width, height, options = {}) {
    destroy()
    _container.value = container

    const ForceGraph3D = (await import('3d-force-graph')).default
    const THREE = await import('three')

    // Create a canvas-based text sprite for node labels
    function _createTextSprite(text, color) {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      canvas.width = 256
      canvas.height = 64
      ctx.font = 'bold 28px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = color
      ctx.globalAlpha = 0.85
      // Truncate long labels
      const label = text.length > 20 ? text.substring(0, 18) + '\u2026' : text
      ctx.fillText(label, 128, 32)

      const texture = new THREE.CanvasTexture(canvas)
      texture.needsUpdate = true
      const spriteMat = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
      })
      const sprite = new THREE.Sprite(spriteMat)
      sprite.scale.set(12, 3, 1)
      return sprite
    }

    const graph = ForceGraph3D()(container)
      .width(width)
      .height(height)
      .backgroundColor('#0a0a1a')

    // Node connection count map for sizing
    const connectionCounts = new Map()
    graphData.edges.forEach(e => {
      const sid = typeof e.source === 'object' ? e.source.id : e.source
      const tid = typeof e.target === 'object' ? e.target.id : e.target
      connectionCounts.set(sid, (connectionCounts.get(sid) || 0) + 1)
      connectionCounts.set(tid, (connectionCounts.get(tid) || 0) + 1)
    })

    const totalNodes = graphData.nodes.length
    const geoType = getGeometryType(totalNodes)

    // Node rendering
    graph.nodeThreeObject(node => {
      const count = connectionCounts.get(node.id) || 0
      const radius = getNodeRadius(count)
      const color = NEON_COLORS[node.type] || NEON_COLORS.Concept || '#6366f1'

      const geometry = geoType === 'sphere'
        ? new THREE.SphereGeometry(radius, RENDER_CONFIG_3D.sphereSegments, RENDER_CONFIG_3D.sphereSegments)
        : new THREE.IcosahedronGeometry(radius, RENDER_CONFIG_3D.icosahedronDetail)

      const matConfig = createNodeMaterial(color, { glow: options.glowEnabled !== false })
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(matConfig.color),
        emissive: new THREE.Color(matConfig.emissive),
        emissiveIntensity: matConfig.emissiveIntensity,
        transparent: matConfig.transparent,
        opacity: matConfig.opacity,
        roughness: matConfig.roughness,
        metalness: matConfig.metalness,
      })

      const mesh = new THREE.Mesh(geometry, material)

      // Glow shell
      if (options.glowEnabled !== false) {
        const glowGeo = geoType === 'sphere'
          ? new THREE.SphereGeometry(radius * 1.3, 16, 16)
          : new THREE.IcosahedronGeometry(radius * 1.3, 0)
        const glowMat = new THREE.MeshBasicMaterial({
          color: new THREE.Color(color),
          transparent: true,
          opacity: 0.15,
          side: THREE.BackSide,
        })
        mesh.add(new THREE.Mesh(glowGeo, glowMat))
      }

      const group = new THREE.Group()
      group.add(mesh)

      // Add text label below the sphere
      const labelSprite = _createTextSprite(node.id || node.name || '', '#ffffff')
      labelSprite.position.set(0, -(radius + 2.5), 0)
      group.add(labelSprite)

      return group
    })
    graph.nodeThreeObjectExtend(false)
    graph.nodeLabel(node => node.id)

    // Connection style
    _applyConnectionStyle(graph, options.connectionStyle || CONNECTION_STYLES.CURVED, graphData)

    // Edge width from weight
    graph.linkWidth(link => getEdgeWidth(link.weight || 0.5))
    graph.linkOpacity(0.45)

    // Force configuration
    graph.d3AlphaDecay(0.02)
    graph.d3Force('charge', (await import('d3-force-3d')).forceManyBody().strength(-80))

    // Load data
    graph.graphData({
      nodes: graphData.nodes.map(n => ({ ...n })),
      links: graphData.edges.map(e => ({
        source: typeof e.source === 'object' ? e.source.id : e.source,
        target: typeof e.target === 'object' ? e.target.id : e.target,
        weight: e.weight || 0.5,
        label: e.label,
      })),
    })

    // Orbit controls config
    const controls = graph.controls()
    controls.enableDamping = true
    controls.dampingFactor = RENDER_CONFIG_3D.orbitDamping
    controls.autoRotate = options.autoRotate || false
    controls.autoRotateSpeed = RENDER_CONFIG_3D.autoRotateSpeed
    controls.maxDistance = RENDER_CONFIG_3D.maxCameraDistance
    controls.minDistance = RENDER_CONFIG_3D.minCameraDistance

    // Lighting
    const scene = graph.scene()
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambientLight)
    const pointLight = new THREE.PointLight(0xffffff, 0.8)
    pointLight.position.set(200, 200, 200)
    scene.add(pointLight)

    // Pulse animation loop
    if (options.pulseEnabled !== false && totalNodes < RENDER_CONFIG_3D.pulseDisableThreshold) {
      const startTime = performance.now()
      const animate = () => {
        _animationFrame.value = requestAnimationFrame(animate)
        _trackFps()
        const scale = getPulseScale(performance.now() - startTime)
        const { nodes: currentNodes } = graph.graphData()
        currentNodes.forEach(node => {
          const obj = node.__threeObj
          if (obj) obj.scale.setScalar(scale)
        })
      }
      animate()
    }

    _graph.value = graph
  }

  function _applyConnectionStyle(graph, style, graphData) {
    switch (style) {
      case CONNECTION_STYLES.PARTICLE:
        graph.linkCurvature(0)
        graph.linkDirectionalParticles(link => {
          const cfg = getParticleConfig(link.weight || 0.5)
          return cfg.emissionRate
        })
        graph.linkDirectionalParticleSpeed(link => {
          const cfg = getParticleConfig(link.weight || 0.5)
          return cfg.speed * 0.001
        })
        break

      case CONNECTION_STYLES.CURVED:
        graph.linkCurvature(link => {
          return getCurvedConfig(link.weight || 0.5).curvature
        })
        graph.linkDirectionalParticles(0)
        break

      case CONNECTION_STYLES.NEURON:
        graph.linkCurvature(link => {
          const cfg = getNeuronConfig(link.weight || 0.5)
          return cfg.curvature
        })
        graph.linkDirectionalParticles(link => {
          const cfg = getNeuronConfig(link.weight || 0.5)
          return cfg.emissionRate
        })
        graph.linkDirectionalParticleSpeed(link => {
          const cfg = getNeuronConfig(link.weight || 0.5)
          return cfg.speed * 0.001
        })
        break

      case CONNECTION_STYLES.ADAPTIVE:
      default:
        graph.linkCurvature(link => getCurvedConfig(link.weight || 0.5).curvature)
        graph.linkDirectionalParticles(0)
        break
    }
  }

  function update(options) {
    if (!_graph.value) return

    if (options.autoRotate !== undefined) {
      _graph.value.controls().autoRotate = options.autoRotate
    }

    if (options.connectionStyle) {
      _applyConnectionStyle(_graph.value, options.connectionStyle, _graph.value.graphData())
    }
  }

  function resize(width, height) {
    if (!_graph.value) return
    _graph.value.width(width).height(height)
  }

  function onNodeClick(callback) {
    if (!_graph.value) return
    _graph.value.onNodeClick(callback)
  }

  function onNodeHover(callback) {
    if (!_graph.value) return
    _graph.value.onNodeHover(callback)
  }

  function diveIn(node) {
    if (!_graph.value) return
    const camera = _graph.value.camera()
    const target = computeDiveInTarget(
      node,
      camera.position,
      RENDER_CONFIG_3D.diveInDistance,
    )
    _graph.value.cameraPosition(target.x, target.y, target.z, RENDER_CONFIG_3D.diveInDuration)
    _isDivedIn.value = true
  }

  function exitDiveIn() {
    if (!_graph.value) return
    const dist = RENDER_CONFIG_3D.cameraDistance
    _graph.value.cameraPosition(0, 0, dist, RENDER_CONFIG_3D.diveInDuration)
    _isDivedIn.value = false
  }

  function highlightNodes(nodeIds) {
    if (!_graph.value) return
    const { nodes } = _graph.value.graphData()
    nodes.forEach(node => {
      const obj = node.__threeObj
      if (!obj) return
      const isHighlighted = !nodeIds || nodeIds.has(node.id)
      if (obj.material) {
        obj.material.opacity = isHighlighted ? 0.9 : 0.1
        obj.material.emissiveIntensity = isHighlighted ? 0.6 : 0.1
      }
    })
  }

  function highlightEdges(edgeKeys) {
    if (!_graph.value) return
    _graph.value.linkOpacity(link => {
      const key = `${link.source.id || link.source}->${link.target.id || link.target}`
      const reverseKey = `${link.target.id || link.target}->${link.source.id || link.source}`
      return edgeKeys && (edgeKeys.has(key) || edgeKeys.has(reverseKey)) ? 1.0 : 0.1
    })
    _graph.value.linkWidth(link => {
      const key = `${link.source.id || link.source}->${link.target.id || link.target}`
      const reverseKey = `${link.target.id || link.target}->${link.source.id || link.source}`
      const isHighlighted = edgeKeys && (edgeKeys.has(key) || edgeKeys.has(reverseKey))
      return isHighlighted ? getEdgeWidth(link.weight || 0.5) * 2 : getEdgeWidth(link.weight || 0.5)
    })
  }

  function clearHighlights() {
    highlightNodes(null)
    if (_graph.value) {
      _graph.value.linkOpacity(0.45)
      _graph.value.linkWidth(link => getEdgeWidth(link.weight || 0.5))
    }
  }

  function getGraphData() {
    return _graph.value ? _graph.value.graphData() : null
  }

  function getCamera() {
    return _graph.value ? _graph.value.camera() : null
  }

  function getFps() {
    return _fps.value
  }

  function isDivedIn() {
    return _isDivedIn.value
  }

  function destroy() {
    if (_animationFrame.value) {
      cancelAnimationFrame(_animationFrame.value)
      _animationFrame.value = null
    }
    if (_graph.value) {
      _graph.value._destructor()
      _graph.value = null
    }
    _container.value = null
    _isDivedIn.value = false
  }

  return {
    render,
    update,
    resize,
    destroy,
    onNodeClick,
    onNodeHover,
    diveIn,
    exitDiveIn,
    highlightNodes,
    highlightEdges,
    clearHighlights,
    getGraphData,
    getCamera,
    getFps,
    isDivedIn,
  }
}
