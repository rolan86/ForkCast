/**
 * Hybrid Renderer
 *
 * Combines Canvas (for edges) and SVG (for nodes) for optimal performance
 * with medium-sized graphs (100-300 nodes).
 *
 * Layer structure:
 * - Layer 0: Canvas for edges (bottom)
 * - Layer 1: SVG for nodes (top, interactive)
 * - Layer 2: SVG for labels (top, with nodes)
 */

import * as d3 from 'd3'
import { drawGlowingEdgeCanvas, getEdgeColor } from './edgeRenderer.js'
import { NEON_COLORS } from '@/constants/graph.js'

/**
 * Render graph using hybrid approach
 *
 * @param {Object} graph - Graph data with nodes and edges
 * @param {HTMLElement} container - Container element
 * @param {Object} options - Rendering options
 * @returns {Object} Render context with cleanup function
 */
export function renderHybrid(graph, container, options = {}) {
  const {
    width = container.clientWidth,
    height = container.clientHeight || 500,
    onNodeClick = null,
    onNodeHover = null,
    enableAnimations = true,
    visualMode = '2.5d',
  } = options

  const is25D = visualMode === '2.5d'

  // Clear existing content
  d3.select(container).selectAll('*').remove()

  // Create container div for layering
  const containerDiv = d3.select(container)
    .append('div')
    .attr('class', 'hybrid-render-container')
    .style('position', 'relative')
    .style('width', `${width}px`)
    .style('height', `${height}px`)

  // Layer 0: Canvas for edges
  const edgeCanvas = containerDiv
    .append('canvas')
    .attr('class', 'edge-layer')
    .attr('width', width)
    .attr('height', height)
    .style('position', 'absolute')
    .style('top', '0')
    .style('left', '0')
    .style('z-index', '0')
    .style('pointer-events', 'none')

  const edgeCtx = edgeCanvas.node().getContext('2d')

  // Layer 1: SVG for nodes
  const nodeSvg = containerDiv
    .append('svg')
    .attr('class', 'node-layer')
    .attr('width', width)
    .attr('height', height)
    .style('position', 'absolute')
    .style('top', '0')
    .style('left', '0')
    .style('z-index', '1')
    .style('pointer-events', 'all')

  // Create group for zoom/pan
  const g = nodeSvg.append('g')

  // Set up zoom behavior
  const zoom = d3.zoom()
    .scaleExtent([0.3, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
      // Redraw edges with transform
      renderEdges(edgeCtx, graph.edges, event.transform, is25D)
    })

  nodeSvg.call(zoom)

  // Render initial edges
  renderEdges(edgeCtx, graph.edges, d3.zoomIdentity, is25D)

  // Render nodes
  const nodeRadius = (d) => {
    const connCount = graph.edges.filter(e =>
      (e.source.id || e.source) === d.id || (e.target.id || e.target) === d.id
    ).length
    return 8 + Math.min(connCount * 1.5, 12)
  }

  const nodes = g.selectAll('.node')
    .data(graph.nodes)
    .join('circle')
    .attr('class', 'node')
    .attr('cx', d => d.x)
    .attr('cy', d => d.y)
    .attr('r', d => nodeRadius(d))
    .attr('fill', d => NEON_COLORS[d.type] || '#6366f1')
    .attr('opacity', enableAnimations ? 0 : 0.85)
    .attr('cursor', 'pointer')
    .style('filter', is25D ? 'drop-shadow(0 0 8px currentColor)' : 'none')

  // Add event handlers
  if (onNodeClick) {
    nodes.on('click', (event, d) => onNodeClick(d, event))
  }

  if (onNodeHover) {
    nodes
      .on('mouseenter', (event, d) => onNodeHover(d, 'enter', event))
      .on('mouseleave', (event, d) => onNodeHover(d, 'leave', event))
  }

  // Add drag behavior
  nodes.call(d3.drag()
    .on('start', dragStarted)
    .on('drag', dragged)
    .on('end', dragEnded)
  )

  // Animate nodes in
  if (enableAnimations) {
    nodes
      .transition()
      .delay((d, i) => 500 + i * 20)
      .duration(200)
      .attr('opacity', 0.85)
  }

  // Drag functions
  let simulation = null

  function dragStarted(event, d) {
    if (!event.active && simulation) simulation.alphaTarget(0.3).restart()
    d.fx = d.x
    d.fy = d.y
  }

  function dragged(event, d) {
    d.fx = event.x
    d.fy = event.y
    // Update node position
    d3.select(this)
      .attr('cx', d.x)
      .attr('cy', d.y)
    // Redraw edges
    renderEdges(edgeCtx, graph.edges, d3.zoomTransform(nodeSvg.node()), is25D)
  }

  function dragEnded(event, d) {
    if (!event.active && simulation) simulation.alphaTarget(0)
    d.fx = null
    d.fy = null
  }

  // Return render context
  return {
    container: containerDiv,
    edgeCanvas,
    edgeCtx,
    nodeSvg,
    g,
    nodes,
    zoom,

    /**
     * Update node positions
     */
    updateNodes(nodeData) {
      nodes.data(nodeData)
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
    },

    /**
     * Update edge positions and redraw
     */
    updateEdges(edgeData) {
      graph.edges = edgeData
      renderEdges(edgeCtx, edgeData, d3.zoomTransform(nodeSvg.node()), is25D)
    },

    /**
     * Set simulation for drag behavior
     */
    setSimulation(sim) {
      simulation = sim
    },

    /**
     * Apply zoom transform
     */
    applyZoom(transform) {
      g.attr('transform', transform)
      renderEdges(edgeCtx, graph.edges, transform, is25D)
    },

    /**
     * Clean up resources
     */
    destroy() {
      d3.select(container).selectAll('*').remove()
    },
  }
}

/**
 * Render edges on canvas
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {Array} edges - Array of edge objects
 * @param {Object} transform - D3 zoom transform
 */
function renderEdges(ctx, edges, transform, is25D = true) {
  const { k, x, y } = transform

  // Clear canvas
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Apply transform
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(k, k)

  // Draw edges
  edges.forEach(edge => {
    const source = edge.source
    const target = edge.target

    // Skip if positions not set
    if (source.x == null || target.x == null) return

    const color = getEdgeColor(edge, edges.map(e => e.source).concat(edges.map(e => e.target)))

    if (is25D) {
      // 2.5D mode: gradient + glow
      const gradient = ctx.createLinearGradient(source.x, source.y, target.x, target.y)
      gradient.addColorStop(0, hexToRgba(color, 0.8))
      gradient.addColorStop(1, hexToRgba(color, 0.2))
      ctx.strokeStyle = gradient
      ctx.shadowColor = color
      ctx.shadowBlur = 6 / k
    } else {
      // 2D mode: flat, no glow
      ctx.strokeStyle = hexToRgba(color, 0.5)
      ctx.shadowColor = 'transparent'
      ctx.shadowBlur = 0
    }

    ctx.lineWidth = 1.5 / k
    ctx.beginPath()
    ctx.moveTo(source.x, source.y)
    ctx.lineTo(target.x, target.y)
    ctx.stroke()
  })

  ctx.restore()
}

/**
 * Convert hex color to RGBA
 */
function hexToRgba(hex, alpha = 1) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Create hybrid renderer with force simulation
 *
 * @param {Object} graph - Graph data
 * @param {HTMLElement} container - Container element
 * @param {Object} simulation - D3 force simulation
 * @param {Object} options - Rendering options
 * @returns {Object} Render context
 */
export function renderHybridWithSimulation(graph, container, simulation, options = {}) {
  const renderer = renderHybrid(graph, container, options)
  renderer.setSimulation(simulation)

  // Update on simulation tick
  simulation.on('tick', () => {
    renderer.updateNodes(graph.nodes)
    renderer.updateEdges(graph.edges)
  })

  return renderer
}
