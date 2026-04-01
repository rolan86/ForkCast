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
