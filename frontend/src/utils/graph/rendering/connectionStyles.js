import { CONNECTION_STYLES, ADAPTIVE_THRESHOLDS } from '@/constants/graph.js'

export function getCurvedConfig(weight) {
  const curvature = 0.4 * (1 - Math.min(weight, 1))
  return {
    curvature: Math.max(0.05, curvature),
    opacityRange: [0.3, 0.6],
  }
}

export function getParticleConfig(weight) {
  const w = Math.max(0.1, Math.min(weight, 1))
  return {
    speed: 2 + w * 6,
    emissionRate: 1 + w * 2,
    particleWidth: 1.5,
  }
}

/**
 * Config for neuron firing style — lightning arcs between nodes.
 * @param {number} weight — edge weight 0..1
 */
export function getNeuronConfig(weight) {
  const w = Math.max(0.1, Math.min(weight, 1))
  return {
    generations: 5,
    displacement: 0.35 + (1 - w) * 0.15,
    roughness: 0.55,
    glowOpacity: 0.15 + w * 0.2,
    restrikeInterval: 60 + (1 - w) * 100,
  }
}

/**
 * Build two perpendicular unit vectors to a direction vector.
 * Pure helper — no Three.js dependency.
 */
function _perpendicularBasis(dx, dy, dz) {
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz)
  if (len < 0.001) return null

  const nx = dx / len, ny = dy / len, nz = dz / len

  // Cross with an axis not parallel to direction
  const ax = Math.abs(nx) < 0.9 ? 1 : 0
  const ay = Math.abs(nx) < 0.9 ? 0 : 1

  const p1x = ny * 0 - nz * ay
  const p1y = nz * ax - nx * 0
  const p1z = nx * ay - ny * ax
  const p1len = Math.sqrt(p1x * p1x + p1y * p1y + p1z * p1z) || 1
  const u1 = { x: p1x / p1len, y: p1y / p1len, z: p1z / p1len }

  const u2 = {
    x: ny * u1.z - nz * u1.y,
    y: nz * u1.x - nx * u1.z,
    z: nx * u1.y - ny * u1.x,
  }

  return { u1, u2 }
}

/**
 * Generate lightning bolt points using recursive midpoint displacement.
 * Each recursion halves the segment and reduces displacement by the roughness
 * factor, creating the characteristic "large bends + fine detail" hierarchy
 * that makes lightning look realistic.
 *
 * @param {{ x: number, y: number, z: number }} start
 * @param {{ x: number, y: number, z: number }} end
 * @param {number} generations — recursion depth (5 = ~32 segments)
 * @param {number} displacement — initial displacement as fraction of segment length
 * @param {number} roughness — decay factor per generation (0.5–0.7)
 * @param {function} [rng] — random number generator (0..1)
 * @returns {Array<{ x: number, y: number, z: number }>}
 */
export function generateLightningPath(start, end, generations, displacement, roughness = 0.55, rng = Math.random) {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const dz = end.z - start.z
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz)
  if (len < 0.001) return [start, end]

  const basis = _perpendicularBasis(dx, dy, dz)
  if (!basis) return [start, end]

  // Iterative midpoint displacement (avoids deep recursion)
  let points = [
    { x: start.x, y: start.y, z: start.z },
    { x: end.x, y: end.y, z: end.z },
  ]

  let currentDisplacement = displacement

  for (let gen = 0; gen < generations; gen++) {
    const newPoints = [points[0]]

    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i]
      const b = points[i + 1]

      // Midpoint
      const mx = (a.x + b.x) * 0.5
      const my = (a.y + b.y) * 0.5
      const mz = (a.z + b.z) * 0.5

      // Segment length for displacement scaling
      const segDx = b.x - a.x
      const segDy = b.y - a.y
      const segDz = b.z - a.z
      const segLen = Math.sqrt(segDx * segDx + segDy * segDy + segDz * segDz)

      // Displace perpendicular to the ORIGINAL direction (not segment direction)
      // This keeps the bolt's overall shape coherent
      const offsetScale = currentDisplacement * segLen
      const offsetA = (rng() - 0.5) * 2 * offsetScale
      const offsetB = (rng() - 0.5) * 2 * offsetScale

      newPoints.push({
        x: mx + basis.u1.x * offsetA + basis.u2.x * offsetB,
        y: my + basis.u1.y * offsetA + basis.u2.y * offsetB,
        z: mz + basis.u1.z * offsetA + basis.u2.z * offsetB,
      })
      newPoints.push(b)
    }

    points = newPoints
    currentDisplacement *= roughness
  }

  return points
}

export function getAdaptiveStyle(cameraDistance) {
  if (cameraDistance > ADAPTIVE_THRESHOLDS.overviewDistance) return 'straight'
  if (cameraDistance > ADAPTIVE_THRESHOLDS.closeUpDistance) return CONNECTION_STYLES.CURVED
  return CONNECTION_STYLES.PARTICLE
}

export function getEdgeWidth(weight) {
  return 0.3 + Math.min(weight, 2) * 1.5
}

export function getEdgeOpacity({ highlighted = false, filtered = false } = {}) {
  if (highlighted) return 1.0
  if (filtered) return 0.05
  return 0.45
}
