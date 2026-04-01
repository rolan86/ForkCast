import { RENDER_CONFIG_3D } from '@/constants/graph.js'

export function screenToNDC(screenX, screenY, containerWidth, containerHeight) {
  return {
    x: (screenX / containerWidth) * 2 - 1,
    y: -(screenY / containerHeight) * 2 + 1,
  }
}

export function isPointInPolygon(point, polygon) {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y
    const xj = polygon[j].x, yj = polygon[j].y
    const intersect =
      yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

export function computeDiveInTarget(node, currentCameraPos, distance) {
  const dx = currentCameraPos.x - node.x
  const dy = currentCameraPos.y - node.y
  const dz = currentCameraPos.z - node.z
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz)
  if (len === 0) return { x: node.x, y: node.y, z: node.z + distance }
  const scale = distance / len
  return {
    x: node.x + dx * scale,
    y: node.y + dy * scale,
    z: node.z + dz * scale,
  }
}

export function projectToScreen(worldPos, camera, containerWidth, containerHeight) {
  return {
    x: (worldPos.x + 1) * containerWidth / 2,
    y: (-worldPos.y + 1) * containerHeight / 2,
  }
}

export function computePathHighlightSet(path) {
  const nodeIds = new Set(path)
  const edgeKeys = new Set()
  for (let i = 0; i < path.length - 1; i++) {
    edgeKeys.add(`${path[i]}->${path[i + 1]}`)
  }
  return { nodeIds, edgeKeys }
}
