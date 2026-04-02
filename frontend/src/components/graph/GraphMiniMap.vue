<!--
GraphMiniMap Component

Mini-map navigation for the graph visualization.
Shows all nodes as colored dots with a viewport indicator.

@emits navigate-to - Emitted when user drags the viewport indicator
-->

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as d3 from 'd3'
import { NEON_COLORS } from '@/constants/graph.js'

// Props
const props = defineProps({
  nodes: {
    type: Array,
    default: () => [],
  },
  viewport: {
    type: Object,
    default: () => ({ x: 0, y: 0, w: 0, h: 0 }),
  },
  mainViewBounds: {
    type: Object,
    default: () => ({ x: 0, y: 0, w: 0, h: 0 }),
  },
  visualMode: {
    type: String,
    default: '2d',
  },
})

// Emits
const emit = defineEmits(['navigate-to'])

// Refs
const container = ref(null)

// Mini-map dimensions
const MINIMAP_SIZE = 150
const PADDING = 10

// D3 references
let svg = null
let viewportRect = null

onMounted(() => {
  renderMiniMap()
})

onUnmounted(() => {
  // Clean up D3 selections
  if (svg) {
    d3.select(svg).selectAll('*').remove()
  }
})

// Watch for nodes, viewport, or visualMode changes
watch([() => props.nodes, () => props.viewport, () => props.visualMode], () => {
  if (container.value) {
    renderMiniMap()
  }
}, { deep: true })

function renderMiniMap() {
  if (!container.value || !props.nodes.length) return

  const { nodes, visualMode } = props

  // Clear previous rendering
  d3.select(container.value).selectAll('*').remove()

  // Check if we're in 3D mode for top-down projection
  if (visualMode === '3d') {
    render3DTopDownProjection(nodes)
  } else {
    render2DMiniMap(nodes)
  }
}

function render2DMiniMap(nodes) {
  const { mainViewBounds } = props

  // Calculate scale to fit graph in mini-map
  const graphBounds = calculateGraphBounds(nodes)
  const scale = (MINIMAP_SIZE - PADDING * 2) / Math.max(graphBounds.width, graphBounds.height)

  // Create SVG
  svg = d3.select(container.value)
    .append('svg')
    .attr('width', MINIMAP_SIZE)
    .attr('height', MINIMAP_SIZE)
    .attr('viewBox', `0 0 ${MINIMAP_SIZE} ${MINIMAP_SIZE}`)

  // Create group with padding
  const g = svg.append('g')
    .attr('transform', `translate(${PADDING}, ${PADDING})`)

  // Render nodes as dots
  const nodeRadius = 2
  g.selectAll('.mm-node')
    .data(nodes)
    .join('circle')
    .attr('class', 'mm-node')
    .attr('cx', d => (d.x - graphBounds.minX) * scale)
    .attr('cy', d => (d.y - graphBounds.minY) * scale)
    .attr('r', nodeRadius)
    .attr('fill', d => NEON_COLORS[d.type] || '#6366f1')
    .attr('opacity', 0.7)

  // Add viewport indicator
  updateViewportIndicator(g, scale, graphBounds)
}

function render3DTopDownProjection(nodes) {
  // Calculate bounds for 3D projection (x-z plane)
  const bounds3D = calculate3DBounds(nodes)
  const scale = (MINIMAP_SIZE - PADDING * 2) / Math.max(bounds3D.width, bounds3D.depth)

  // Create SVG
  svg = d3.select(container.value)
    .append('svg')
    .attr('width', MINIMAP_SIZE)
    .attr('height', MINIMAP_SIZE)
    .attr('viewBox', `0 0 ${MINIMAP_SIZE} ${MINIMAP_SIZE}`)

  // Create group with padding
  const g = svg.append('g')
    .attr('transform', `translate(${PADDING}, ${PADDING})`)

  // Render nodes as dots using x-z projection
  const nodeRadius = 2
  g.selectAll('.mm-node-3d')
    .data(nodes)
    .join('circle')
    .attr('class', 'mm-node-3d')
    .attr('cx', d => ((d.x || 0) - bounds3D.minX) * scale)
    .attr('cy', d => ((d.z || 0) - bounds3D.minZ) * scale)
    .attr('r', nodeRadius)
    .attr('fill', d => NEON_COLORS[d.type] || '#6366f1')
    .attr('opacity', 0.7)

  // Add label "Top-down view"
  g.append('text')
    .attr('class', 'top-down-label')
    .attr('x', (MINIMAP_SIZE - PADDING * 2) / 2)
    .attr('y', (MINIMAP_SIZE - PADDING * 2) - 5)
    .attr('text-anchor', 'middle')
    .attr('font-size', '10px')
    .attr('fill', 'var(--text-secondary)')
    .attr('opacity', 0.6)
    .text('Top-down')
}

function updateViewportIndicator(g, scale, graphBounds) {
  // Remove existing viewport indicator
  g.selectAll('.mm-viewport').remove()

  const { viewport, mainViewBounds } = props

  // Only show if we have valid viewport and bounds
  if (viewport.w <= 0 || viewport.h <= 0 || mainViewBounds.w <= 0 || mainViewBounds.h <= 0) {
    return
  }

  // Calculate viewport position in mini-map coordinates
  const viewportX = ((viewport.x - graphBounds.minX) * scale) + PADDING
  const viewportY = ((viewport.y - graphBounds.minY) * scale) + PADDING
  const viewportW = (viewport.w * scale)
  const viewportH = (viewport.h * scale)

  // Read CSS variable for primary color at render time
  const primaryColor = getComputedStyle(container.value).getPropertyValue('--color-primary').trim()
  const fillColor = d3.color(primaryColor)
  if (fillColor) fillColor.opacity = 0.1

  // Create viewport indicator rectangle
  viewportRect = g.append('rect')
    .attr('class', 'mm-viewport')
    .attr('x', viewportX)
    .attr('y', viewportY)
    .attr('width', viewportW)
    .attr('height', viewportH)
    .attr('fill', fillColor ? fillColor.toString() : 'rgba(99, 102, 241, 0.1)')
    .attr('stroke', primaryColor || '#6366f1')
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', '4, 2')
    .attr('rx', 2)
    .style('cursor', 'move')
    .style('filter', `drop-shadow(0 0 6px ${primaryColor || '#6366f1'})`)

  // Add drag behavior to viewport indicator
  viewportRect.call(d3.drag()
    .on('drag', (event) => {
      // Calculate new viewport position based on drag delta
      const newX = (event.x - PADDING) / scale + graphBounds.minX
      const newY = (event.y - PADDING) / scale + graphBounds.minY

      // Constrain to graph bounds
      const constrainedX = Math.max(graphBounds.minX, Math.min(newX, graphBounds.maxX - viewport.w))
      const constrainedY = Math.max(graphBounds.minY, Math.min(newY, graphBounds.maxY - viewport.h))

      emit('navigate-to', {
        x: constrainedX,
        y: constrainedY,
      })
    })
  )
}

function calculateGraphBounds(nodes) {
  if (!nodes.length) {
    return { minX: 0, minY: 0, maxX: 100, maxY: 100, width: 100, height: 100 }
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  nodes.forEach(node => {
    if (node.x !== undefined) {
      minX = Math.min(minX, node.x)
      maxX = Math.max(maxX, node.x)
    }
    if (node.y !== undefined) {
      minY = Math.min(minY, node.y)
      maxY = Math.max(maxY, node.y)
    }
  })

  // Handle edge case
  if (minX === Infinity) minX = 0
  if (minY === Infinity) minY = 0
  if (maxX === -Infinity) maxX = 100
  if (maxY === -Infinity) maxY = 100

  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX || 100,
    height: maxY - minY || 100,
  }
}

function calculate3DBounds(nodes) {
  if (!nodes.length) {
    return { minX: 0, minZ: 0, maxX: 100, maxZ: 100, width: 100, depth: 100 }
  }

  let minX = Infinity
  let minZ = Infinity
  let maxX = -Infinity
  let maxZ = -Infinity

  nodes.forEach(node => {
    if (node.x !== undefined) {
      minX = Math.min(minX, node.x)
      maxX = Math.max(maxX, node.x)
    }
    if (node.z !== undefined) {
      minZ = Math.min(minZ, node.z)
      maxZ = Math.max(maxZ, node.z)
    }
  })

  // Handle edge case
  if (minX === Infinity) minX = 0
  if (minZ === Infinity) minZ = 0
  if (maxX === -Infinity) maxX = 100
  if (maxZ === -Infinity) maxZ = 100

  return {
    minX,
    minZ,
    maxX,
    maxZ,
    width: maxX - minX || 100,
    depth: maxZ - minZ || 100,
  }
}
</script>

<template>
  <div
    ref="container"
    class="mini-map"
    :style="{
      width: `${MINIMAP_SIZE}px`,
      height: `${MINIMAP_SIZE}px`
    }"
  >
    <!-- SVG will be rendered here by D3 -->
  </div>
</template>

<style scoped>
.mini-map {
  position: relative;
  background: var(--surface-raised);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.3),
    inset 0 0 20px color-mix(in srgb, var(--color-primary) 5%, transparent);
  overflow: hidden;
}

.mm-node {
  transition: opacity 150ms ease-out;
}

.mm-node:hover {
  opacity: 1 !important;
}

.mm-viewport {
  animation: viewport-pulse 2s infinite;
  transition: fill 150ms ease-out;
}

.mm-viewport:hover {
  fill: color-mix(in srgb, var(--color-primary) 20%, transparent);
}

@keyframes viewport-pulse {
  0%, 100% {
    opacity: 0.8;
    stroke-opacity: 0.8;
  }
  50% {
    opacity: 1;
    stroke-opacity: 1;
  }
}
</style>
