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
 * @returns {{ segments: number, jitter: number, glowOpacity: number, restrikeInterval: number }}
 */
export function getNeuronConfig(weight) {
  const w = Math.max(0.1, Math.min(weight, 1))
  return {
    segments: 12 + Math.floor(w * 8),
    jitter: 1.5 + (1 - w) * 2.5,
    glowOpacity: 0.3 + w * 0.4,
    restrikeInterval: 80 + (1 - w) * 120,
  }
}

/**
 * Generate jagged lightning bolt points between two 3D positions.
 * Pure function — no Three.js dependency. Returns array of {x,y,z} points.
 *
 * @param {{ x: number, y: number, z: number }} start
 * @param {{ x: number, y: number, z: number }} end
 * @param {number} segments — number of intermediate points
 * @param {number} jitter — max perpendicular displacement
 * @param {function} [rng] — random number generator (0..1), defaults to Math.random
 * @returns {Array<{ x: number, y: number, z: number }>}
 */
export function generateLightningPath(start, end, segments, jitter, rng = Math.random) {
  const points = [{ x: start.x, y: start.y, z: start.z }]

  const dx = end.x - start.x
  const dy = end.y - start.y
  const dz = end.z - start.z

  // Build two perpendicular vectors for displacement
  // Use cross product with an arbitrary axis to get perpendiculars
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz)
  if (len < 0.001) return [start, end]

  const nx = dx / len, ny = dy / len, nz = dz / len

  // Pick an axis not parallel to the direction
  const ax = Math.abs(nx) < 0.9 ? 1 : 0
  const ay = Math.abs(nx) < 0.9 ? 0 : 1

  // perpendicular 1 = direction × arbitrary
  const p1x = ny * 0 - nz * ay
  const p1y = nz * ax - nx * 0
  const p1z = nx * ay - ny * ax
  const p1len = Math.sqrt(p1x * p1x + p1y * p1y + p1z * p1z) || 1
  const u1x = p1x / p1len, u1y = p1y / p1len, u1z = p1z / p1len

  // perpendicular 2 = direction × perp1
  const u2x = ny * u1z - nz * u1y
  const u2y = nz * u1x - nx * u1z
  const u2z = nx * u1y - ny * u1x

  for (let i = 1; i <= segments; i++) {
    const t = i / (segments + 1)
    // Taper jitter toward endpoints (max in middle)
    const envelope = 4 * t * (1 - t)
    const j = jitter * envelope

    const offsetA = (rng() - 0.5) * 2 * j
    const offsetB = (rng() - 0.5) * 2 * j

    points.push({
      x: start.x + dx * t + u1x * offsetA + u2x * offsetB,
      y: start.y + dy * t + u1y * offsetA + u2y * offsetB,
      z: start.z + dz * t + u1z * offsetA + u2z * offsetB,
    })
  }

  points.push({ x: end.x, y: end.y, z: end.z })
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
