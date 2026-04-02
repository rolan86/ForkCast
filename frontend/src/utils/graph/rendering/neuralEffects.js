import { RENDER_CONFIG_3D } from '@/constants/graph.js'

const {
  nodeBaseRadius,
  nodeMaxRadius,
  pulseFrequency,
  pulseAmplitude,
  sphereNodeThreshold,
} = RENDER_CONFIG_3D

export function getNodeRadius(connectionCount) {
  const scaled = nodeBaseRadius + Math.sqrt(connectionCount) * 0.8
  return Math.min(scaled, nodeMaxRadius)
}

export function getPulseScale(timeMs) {
  const timeSec = timeMs / 1000
  return 1 + pulseAmplitude * Math.sin(2 * Math.PI * pulseFrequency * timeSec)
}

export function getGeometryType(totalNodes) {
  return totalNodes < sphereNodeThreshold ? 'sphere' : 'icosahedron'
}

export function createNodeMaterial(color, { glow = true } = {}) {
  return {
    color,
    emissive: color,
    emissiveIntensity: glow ? 0.4 : 0.1,
    transparent: true,
    opacity: 0.9,
    roughness: 0.3,
    metalness: 0.1,
  }
}

export function createGlowMaterial(color) {
  return {
    color,
    transparent: true,
    opacity: 0.15,
    side: 'back',
  }
}

export function createHighlightMaterial(color) {
  return {
    color,
    emissive: color,
    emissiveIntensity: 0.8,
    transparent: true,
    opacity: 1.0,
    roughness: 0.2,
    metalness: 0.2,
  }
}
