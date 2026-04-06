import { ref, shallowRef } from 'vue'

const ACCENT = '#6366f1'
const EDGE_OPACITY = 0.2
const EDGE_MAX_DIST = 180
const REPULSION = 800
const SPRING_K = 0.003
const DAMPING = 0.92
const NODE_RADIUS_SEED = 4
const NODE_RADIUS_AGENT = 6

export function useConstellationCanvas() {
  const nodes = ref([])
  const edges = ref([])
  const state = ref('idle') // idle | building | activating | morphing | done

  let canvas = null
  let ctx = null
  let rafId = null
  let dpr = 1
  let width = 0
  let height = 0
  let morphCallback = null

  function init(canvasEl) {
    canvas = canvasEl
    ctx = canvas.getContext('2d')
    dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1
    resize()
    state.value = 'building'
    tick()
  }

  function resize() {
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    width = rect.width
    height = rect.height
    canvas.width = width * dpr
    canvas.height = height * dpr
    if (ctx) ctx.scale(dpr, dpr)
  }

  function addSeedNode(color) {
    const node = {
      id: `seed_${nodes.value.length}`,
      type: 'seed',
      x: width * 0.2 + Math.random() * width * 0.6,
      y: height * 0.2 + Math.random() * height * 0.6,
      vx: 0,
      vy: 0,
      targetX: null,
      targetY: null,
      radius: NODE_RADIUS_SEED + Math.random() * 2,
      color,
      opacity: 0,
      fadeIn: 0.02,
      pulseAlpha: 0,
      glowRadius: 12,
    }
    nodes.value.push(node)
    rebuildEdges()
  }

  function addAgentNode(agentId) {
    const node = {
      id: agentId,
      type: 'agent',
      x: width * 0.15 + Math.random() * width * 0.7,
      y: height * 0.15 + Math.random() * height * 0.7,
      vx: 0,
      vy: 0,
      targetX: null,
      targetY: null,
      radius: NODE_RADIUS_AGENT,
      color: ACCENT,
      opacity: 0,
      fadeIn: 0.03,
      pulseAlpha: 1.0,
      glowRadius: 20,
    }
    nodes.value.push(node)
    rebuildEdges()
  }

  function rebuildEdges() {
    const newEdges = []
    const ns = nodes.value
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const dx = ns[i].x - ns[j].x
        const dy = ns[i].y - ns[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < EDGE_MAX_DIST) {
          newEdges.push({
            source: i,
            target: j,
            opacity: EDGE_OPACITY * (1 - dist / EDGE_MAX_DIST),
            baseOpacity: EDGE_OPACITY * (1 - dist / EDGE_MAX_DIST),
          })
        }
      }
    }
    edges.value = newEdges
  }

  function activateNetwork() {
    state.value = 'activating'
    // Brighten all edges in a wave
    edges.value.forEach((e, i) => {
      setTimeout(() => {
        e.opacity = Math.min(0.6, e.baseOpacity * 3)
      }, i * 30)
    })
  }

  function computeGridTargets(canvasW, canvasH, count) {
    const cols = 3
    const gap = 12
    const cardW = (canvasW - gap * (cols + 1)) / cols
    const cardH = 72
    const targets = []
    for (let i = 0; i < count; i++) {
      const col = i % cols
      const row = Math.floor(i / cols)
      targets.push({
        x: gap + col * (cardW + gap) + cardW / 2,
        y: gap + row * (cardH + gap) + cardH / 2,
        col,
        row,
      })
    }
    return targets
  }

  function flashAndMorph(targetPositions) {
    // Flash moment: brighten all connections
    edges.value.forEach(e => { e.opacity = 0.6 })
    state.value = 'activating'

    // After 300ms flash + 200ms pause, begin morph
    setTimeout(() => morphToGrid(targetPositions), 500)
  }

  function morphToGrid(targetPositions) {
    state.value = 'morphing'
    const agentNodes = nodes.value.filter(n => n.type === 'agent')
    const startTime = performance.now()
    const duration = 600

    // Assign targets
    agentNodes.forEach((node, i) => {
      if (targetPositions[i]) {
        node.targetX = targetPositions[i].x
        node.targetY = targetPositions[i].y
      }
    })

    // Fade edges
    edges.value.forEach(e => {
      e.opacity = 0
    })

    function morphTick() {
      const elapsed = performance.now() - startTime
      const t = Math.min(1, elapsed / duration)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3)

      agentNodes.forEach(node => {
        if (node.targetX != null) {
          node.x += (node.targetX - node.x) * eased * 0.1
          node.y += (node.targetY - node.y) * eased * 0.1
          node.radius = NODE_RADIUS_AGENT + eased * 4
        }
      })

      if (t >= 1) {
        state.value = 'done'
        if (morphCallback) morphCallback()
        return
      }
      requestAnimationFrame(morphTick)
    }
    requestAnimationFrame(morphTick)
  }

  function onMorphComplete(cb) {
    morphCallback = cb
  }

  // Physics tick
  function applyForces() {
    const ns = nodes.value
    if (state.value === 'morphing' || state.value === 'done') return

    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const dx = ns[i].x - ns[j].x
        const dy = ns[i].y - ns[j].y
        const distSq = dx * dx + dy * dy + 1
        const force = REPULSION / distSq
        const fx = (dx / Math.sqrt(distSq)) * force
        const fy = (dy / Math.sqrt(distSq)) * force
        ns[i].vx += fx
        ns[i].vy += fy
        ns[j].vx -= fx
        ns[j].vy -= fy
      }
    }

    // Spring forces along edges
    edges.value.forEach(e => {
      const a = ns[e.source]
      const b = ns[e.target]
      if (!a || !b) return
      const dx = b.x - a.x
      const dy = b.y - a.y
      const fx = dx * SPRING_K
      const fy = dy * SPRING_K
      a.vx += fx
      a.vy += fy
      b.vx -= fx
      b.vy -= fy
    })

    // Apply velocity + damping + bounds
    ns.forEach(n => {
      n.vx *= DAMPING
      n.vy *= DAMPING
      n.x += n.vx
      n.y += n.vy
      // Keep in bounds
      n.x = Math.max(n.radius, Math.min(width - n.radius, n.x))
      n.y = Math.max(n.radius, Math.min(height - n.radius, n.y))
      // Fade in
      if (n.opacity < 1) n.opacity = Math.min(1, n.opacity + n.fadeIn)
      // Pulse decay
      if (n.pulseAlpha > 0) n.pulseAlpha = Math.max(0, n.pulseAlpha - 0.015)
    })
  }

  function draw() {
    if (!ctx) return
    ctx.clearRect(0, 0, width, height)

    // Background radial glow
    const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, width * 0.5)
    bgGrad.addColorStop(0, 'rgba(99,102,241,0.05)')
    bgGrad.addColorStop(1, 'rgba(99,102,241,0)')
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, width, height)

    // Edges
    const ns = nodes.value
    edges.value.forEach(e => {
      const a = ns[e.source]
      const b = ns[e.target]
      if (!a || !b) return
      ctx.beginPath()
      ctx.strokeStyle = `rgba(99,102,241,${e.opacity * Math.min(a.opacity, b.opacity)})`
      ctx.lineWidth = 0.7
      // Slight curve
      const mx = (a.x + b.x) / 2 + (a.y - b.y) * 0.1
      const my = (a.y + b.y) / 2 + (b.x - a.x) * 0.1
      ctx.moveTo(a.x, a.y)
      ctx.quadraticCurveTo(mx, my, b.x, b.y)
      ctx.stroke()
    })

    // Nodes
    ns.forEach(n => {
      // Pulse glow
      if (n.pulseAlpha > 0) {
        ctx.save()
        ctx.globalAlpha = n.pulseAlpha * 0.4
        ctx.shadowBlur = n.glowRadius * 2
        ctx.shadowColor = n.color
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.radius * 2, 0, Math.PI * 2)
        ctx.fillStyle = n.color
        ctx.fill()
        ctx.restore()
      }

      // Node body
      ctx.save()
      ctx.globalAlpha = n.opacity
      ctx.shadowBlur = n.glowRadius
      ctx.shadowColor = n.color
      ctx.beginPath()
      ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2)
      ctx.fillStyle = n.color
      ctx.fill()
      ctx.restore()
    })
  }

  function tick() {
    if (state.value === 'done') return
    applyForces()
    draw()
    rafId = requestAnimationFrame(tick)
  }

  function destroy() {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    ctx = null
    canvas = null
    nodes.value = []
    edges.value = []
    state.value = 'idle'
  }

  return {
    nodes,
    edges,
    state,
    init,
    resize,
    addSeedNode,
    addAgentNode,
    activateNetwork,
    computeGridTargets,
    flashAndMorph,
    morphToGrid,
    onMorphComplete,
    destroy,
  }
}
