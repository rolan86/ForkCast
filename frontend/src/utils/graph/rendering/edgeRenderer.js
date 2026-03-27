/**
 * Edge Renderer
 *
 * Renders graph edges with gradient and glow effects
 * for the 2.5D holographic visual style.
 *
 * Supports both SVG and Canvas rendering modes.
 */

import { NEON_COLORS } from '@/constants/graph.js'

/**
 * Create an SVG gradient definition for edges
 * Gradient goes from bright at source to dim at target
 * creating a "light beam" effect
 *
 * @param {Object} svg - D3 SVG selection
 * @param {string} id - Gradient ID
 * @param {string} color - Base color for the gradient
 */
export function createEdgeGradient(svg, id, color = '#00d4ff') {
  const defs = svg.select('defs').empty()
    ? svg.append('defs')
    : svg.select('defs')

  defs.append('linearGradient')
    .attr('id', id)
    .attr('gradientUnits', 'userSpaceOnUse')
    .attr('x1', '0%')
    .attr('y1', '0%')
    .attr('x2', '100%')
    .attr('y2', '0%')
    .append('stop')
    .attr('offset', '0%')
    .attr('stop-color', color)
    .attr('stop-opacity', 1)

  defs.select(`#${id}`)
    .append('stop')
    .attr('offset', '100%')
    .attr('stop-color', color)
    .attr('stop-opacity', 0.3)
}

/**
 * Create SVG filter for glow effect
 * Gives edges a "neon tube" appearance
 *
 * @param {Object} svg - D3 SVG selection
 * @param {string} id - Filter ID
 * @param {string} color - Glow color
 */
export function createGlowFilter(svg, id, color = '#00d4ff') {
  const defs = svg.select('defs').empty()
    ? svg.append('defs')
    : svg.select('defs')

  const filter = defs.append('filter')
    .attr('id', id)
    .attr('x', '-50%')
    .attr('y', '-50%')
    .attr('width', '200%')
    .attr('height', '200%')

  // Glow layer
  filter.append('feGaussianBlur')
    .attr('stdDeviation', '2')
    .attr('result', 'coloredBlur')

  const feMerge = filter.append('feMerge')

  feMerge.append('feMergeNode')
    .attr('in', 'coloredBlur')

  feMerge.append('feMergeNode')
    .attr('in', 'SourceGraphic')
}

/**
 * Draw a glowing edge on SVG context
 *
 * @param {Object} selection - D3 selection of edge elements
 * @param {Object} options - Rendering options
 */
export function drawGlowingEdgesSVG(selection, options = {}) {
  const {
    color = '#6366f1',
    width = 1.5,
    opacity = 0.7,
    animated = false,
  } = options

  selection
    .attr('stroke', color)
    .attr('stroke-width', width)
    .attr('opacity', opacity)
    .style('filter', `url(#glow-${color.replace('#', '')})`)

  if (animated) {
    selection
      .attr('stroke-dasharray', '5, 5')
      .style('animation', 'edge-flow 1s linear infinite')
  }
}

/**
 * Draw a glowing edge on Canvas context
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
 * @param {Object} edge - Edge object with source and target positions
 * @param {Object} options - Rendering options
 */
export function drawGlowingEdgeCanvas(ctx, edge, options = {}) {
  const {
    color = '#6366f1',
    width = 1.5,
    opacity = 0.7,
  } = options

  const { source, target } = edge

  // Create gradient
  const gradient = ctx.createLinearGradient(source.x, source.y, target.x, target.y)
  gradient.addColorStop(0, hexToRgba(color, opacity))
  gradient.addColorStop(1, hexToRgba(color, opacity * 0.3))

  // Draw edge with glow
  ctx.save()
  ctx.strokeStyle = gradient
  ctx.lineWidth = width
  ctx.shadowColor = color
  ctx.shadowBlur = 6
  ctx.beginPath()
  ctx.moveTo(source.x, source.y)
  ctx.lineTo(target.x, target.y)
  ctx.stroke()
  ctx.restore()
}

/**
 * Draw all edges on Canvas context
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
 * @param {Array} edges - Array of edge objects
 * @param {Object} options - Rendering options
 */
export function drawAllEdgesCanvas(ctx, edges, options = {}) {
  edges.forEach(edge => {
    drawGlowingEdgeCanvas(ctx, edge, options)
  })
}

/**
 * Get edge color based on connected node types
 * Returns a color that represents the relationship
 *
 * @param {Object} edge - Edge object
 * @param {Object} nodes - Array of all nodes for type lookup
 * @returns {string} Hex color
 */
export function getEdgeColor(edge, nodes) {
  const sourceNode = nodes.find(n => n.id === (edge.source.id || edge.source))
  const targetNode = nodes.find(n => n.id === (edge.target.id || edge.target))

  if (!sourceNode || !targetNode) {
    return '#6366f1' // Default indigo
  }

  // If same type, use that type's color
  if (sourceNode.type === targetNode.type) {
    return NEON_COLORS[sourceNode.type] || '#6366f1'
  }

  // Otherwise, use a neutral color
  return '#6366f1'
}

/**
 * Convert hex color to RGBA string
 *
 * @param {string} hex - Hex color string
 * @param {number} alpha - Alpha value (0-1)
 * @returns {string} RGBA color string
 */
function hexToRgba(hex, alpha = 1) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Highlight edges connected to a specific node
 * Used for hover and selection states
 *
 * @param {Object} selection - D3 selection of edge elements
 * @param {string} nodeId - Node ID to highlight edges for
 * @param {boolean} dimOthers - Whether to dim non-connected edges
 */
export function highlightConnectedEdges(selection, nodeId, dimOthers = true) {
  selection.each(function(edge) {
    const isConnected =
      (edge.source.id || edge.source) === nodeId ||
      (edge.target.id || edge.target) === nodeId

    const elem = d3.select(this)

    if (isConnected) {
      elem
        .attr('opacity', 1)
        .attr('stroke-width', 2.5)
    } else if (dimOthers) {
      elem.attr('opacity', 0.1)
    } else {
      elem
        .attr('opacity', 0.7)
        .attr('stroke-width', 1.5)
    }
  })
}

/**
 * Reset edge styling to default
 *
 * @param {Object} selection - D3 selection of edge elements
 */
export function resetEdgeStyling(selection) {
  selection
    .attr('opacity', 0.7)
    .attr('stroke-width', 1.5)
}
