/**
 * useGraphRenderer Composable
 *
 * Owns all D3 rendering state and operations for the graph visualization.
 * Extracted from GraphTab.vue to enable testability and keep the view thin.
 *
 * Reactive refs (Vue can track):
 * - viewport: current zoom/pan viewport bounds (for mini-map)
 * - connCounts: connection counts per node (for search highlight radius)
 * - isRendering: re-entrancy guard
 * - renderMode: actual render mode in use (may differ from user preference)
 *
 * @composable
 */

import { ref, shallowRef, readonly, onScopeDispose } from 'vue'
import * as d3 from 'd3'
import { NEON_COLORS, PERFORMANCE_THRESHOLDS } from '@/constants/graph.js'
import { renderHybrid } from '@/utils/graph/rendering/hybridRenderer.js'
import { runForceLayoutWithEdgeStrength } from '@/utils/graph/layouts/force.js'
import { runHierarchicalLayout } from '@/utils/graph/layouts/hierarchical.js'
import { runCircularLayout } from '@/utils/graph/layouts/circular.js'
import { runClusteredLayout } from '@/utils/graph/layouts/clustered.js'

export function useGraphRenderer() {
  // Reactive state Vue can track
  const viewport = ref({ x: 0, y: 0, w: 0, h: 0 })
  const connCounts = ref({})
  const isRendering = ref(false)
  const renderMode = ref(null)

  // Internal D3 state (shallowRef so Vue tracks reference changes, not deep)
  const _svgSelection = shallowRef(null)
  const _zoomBehavior = shallowRef(null)
  const _hybridRenderer = shallowRef(null)
  const _simulation = shallowRef(null)
  const _container = shallowRef(null)
  let _resizeObserver = null

  function bind(container, onResize) {
    _container.value = container
    _resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        onResize(entry.contentRect.width, entry.contentRect.height)
      }
    })
    _resizeObserver.observe(container)
  }

  function getDimensions() {
    const container = _container.value
    if (!container) return { width: 800, height: 600 }
    return {
      width: container.clientWidth || 800,
      height: container.clientHeight || 600,
    }
  }

  function _buildConnCounts(edges) {
    const counts = {}
    edges.forEach(e => {
      const src = e.source.id || e.source
      const tgt = e.target.id || e.target
      counts[src] = (counts[src] || 0) + 1
      counts[tgt] = (counts[tgt] || 0) + 1
    })
    connCounts.value = counts
  }

  function nodeRadiusFor(id) {
    return 8 + Math.min((connCounts.value[id] || 0) * 1.5, 12)
  }

  function render(graphData, options) {
    const container = _container.value
    if (!container || !graphData) return

    isRendering.value = true
    const { width, height } = getDimensions()

    // Build connCounts BEFORE any render mode
    _buildConnCounts(graphData.edges)

    // Only auto-select render mode if user hasn't manually chosen one
    let effectiveRenderMode = options.renderMode
    if (!options.userSelectedRenderMode) {
      const nodeCount = graphData.nodes.length
      if (nodeCount < PERFORMANCE_THRESHOLDS.svgMaxNodes) effectiveRenderMode = 'svg'
      else if (nodeCount < PERFORMANCE_THRESHOLDS.hybridMaxNodes) effectiveRenderMode = 'hybrid'
      else effectiveRenderMode = 'canvas'
    }
    renderMode.value = effectiveRenderMode

    // Teardown previous render
    _simulation.value?.stop()
    _hybridRenderer.value?.destroy()

    // Delegate to render strategy
    if (effectiveRenderMode === 'hybrid') {
      _renderHybrid(container, graphData, width, height, options)
    } else {
      _renderLegacy(container, graphData, width, height, options, effectiveRenderMode)
    }

    // Wire zoom to update viewport ref
    if (_svgSelection.value && _zoomBehavior.value) {
      _zoomBehavior.value.on('zoom.viewport', (event) => {
        const t = event.transform
        viewport.value = {
          x: -t.x / t.k,
          y: -t.y / t.k,
          w: width / t.k,
          h: height / t.k,
        }
      })
    }

    isRendering.value = false
  }

  function _renderHybrid(container, graphData, width, height, options) {
    d3.select(container).selectAll('*').remove()

    const nodes = graphData.nodes.map(n => ({ ...n }))
    const edges = graphData.edges.map(e => ({ ...e }))

    const params = options.layoutParams || {}

    _simulation.value = runForceLayoutWithEdgeStrength(nodes, edges, {
      width,
      height,
      linkDistance: params.linkDistance || 80,
      chargeStrength: params.chargeStrength || -200,
      collideRadius: params.collideRadius || 8,
      alphaDecay: 0.02,
      velocityDecay: 0.4,
      typeGravity: 0.1,
      centralBias: 0.05,
      iterations: 0,
    })

    _hybridRenderer.value = renderHybrid(
      { nodes, edges },
      container,
      {
        width,
        height,
        onNodeClick: options.onNodeClick,
        enableAnimations: true,
      }
    )

    _hybridRenderer.value.setSimulation(_simulation.value)
    _svgSelection.value = _hybridRenderer.value.nodeSvg
    _zoomBehavior.value = _hybridRenderer.value.zoom
  }

  function _renderLegacy(container, graphData, width, height, options, mode) {
    d3.select(container).selectAll('*').remove()

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])

    const g = svg.append('g')
    let currentZoomScale = 1

    const zoom = d3.zoom()
      .scaleExtent([0.3, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        currentZoomScale = event.transform.k
        g.selectAll('.node-label').attr('display', currentZoomScale > 1.5 ? 'block' : 'none')
      })
    svg.call(zoom)

    _zoomBehavior.value = zoom
    _svgSelection.value = svg

    const nodes = graphData.nodes.map(n => ({ ...n }))
    const edges = graphData.edges.map(e => ({ ...e }))

    const getNodeColor = options.getNodeColor || ((type) => NEON_COLORS[type] || '#6366f1')
    const params = options.layoutParams || {}
    const useCanvas = mode === 'canvas'

    if (useCanvas) {
      _simulation.value = runForceLayoutWithEdgeStrength(nodes, edges, {
        width,
        height,
        linkDistance: params.linkDistance || 80,
        chargeStrength: params.chargeStrength || -200,
        collideRadius: params.collideRadius || 8,
        alphaDecay: 0.02,
        velocityDecay: 0.4,
        typeGravity: 0.1,
        centralBias: 0.05,
        iterations: 300,
      })

      g.selectAll('line')
        .data(edges)
        .join('line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
        .attr('stroke', 'var(--border)')
        .attr('stroke-width', 1)

      g.selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => nodeRadiusFor(d.id))
        .attr('fill', d => getNodeColor(d.type))
        .attr('opacity', 0.85)
        .on('click', (event, d) => options.onNodeClick(d))
    } else {
      _simulation.value = runForceLayoutWithEdgeStrength(nodes, edges, {
        width,
        height,
        linkDistance: params.linkDistance || 80,
        chargeStrength: params.chargeStrength || -200,
        collideRadius: params.collideRadius || 8,
        alphaDecay: 0.02,
        velocityDecay: 0.4,
        typeGravity: 0.1,
        centralBias: 0.05,
        iterations: 0,
      })

      const link = g.selectAll('line')
        .data(edges)
        .join('line')
        .attr('stroke', 'var(--border)')
        .attr('stroke-width', 1)

      const node = g.selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => nodeRadiusFor(d.id))
        .attr('fill', d => getNodeColor(d.type))
        .attr('opacity', 0.85)
        .attr('cursor', 'pointer')
        .on('click', (event, d) => options.onNodeClick(d))
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) _simulation.value.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) _simulation.value.alphaTarget(0)
            d.fx = null; d.fy = null
          })
        )

      node.append('title').text(d => `${d.id} (${d.type})`)

      const labels = g.selectAll('.node-label')
        .data(nodes)
        .join('text')
        .attr('class', 'node-label')
        .attr('display', 'none')
        .attr('font-size', '10px')
        .attr('font-family', 'var(--font-mono)')
        .attr('fill', 'var(--text-primary)')
        .attr('dx', d => nodeRadiusFor(d.id) + 4)
        .attr('dy', 4)
        .text(d => d.id)

      _simulation.value.on('tick', () => {
        link
          .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
        node
          .attr('cx', d => d.x).attr('cy', d => d.y)
        labels
          .attr('x', d => d.x).attr('y', d => d.y)
      })

      node.attr('opacity', 0)
        .transition()
        .delay((d, i) => 500 + i * 20)
        .duration(200)
        .attr('opacity', 0.85)
    }
  }

  function applyLayout(type, graphData, params = {}) {
    const { width, height } = getDimensions()
    const layoutFns = {
      force: null,
      hierarchical: runHierarchicalLayout,
      circular: runCircularLayout,
      clustered: runClusteredLayout,
    }

    if (type === 'force') return

    const layoutFn = layoutFns[type]
    if (!layoutFn) return

    const result = layoutFn(graphData.nodes, graphData.edges, { width, height, ...params })

    graphData.nodes.forEach(node => {
      const positioned = result.nodes.find(n => n.id === node.id)
      if (positioned) {
        node.x = positioned.x
        node.y = positioned.y
      }
    })

    return result
  }

  function applySearchFilters(graphData, query, filters) {
    const container = _container.value
    if (!container || !graphData) return

    const sel = d3.select(container)
    const q = (query || '').toLowerCase().trim()

    sel.selectAll('circle').each(function (d) {
      const matchesSearch = !q || d.id.toLowerCase().includes(q) || (d.type || '').toLowerCase().includes(q)
      const matchesFilter = !filters.length || filters.includes(d.type)
      const visible = matchesSearch && matchesFilter
      d3.select(this)
        .attr('opacity', visible ? 0.85 : 0.1)
        .attr('r', visible && q && d.id.toLowerCase().includes(q) ? nodeRadiusFor(d.id) * 1.5 : nodeRadiusFor(d.id))
    })
    sel.selectAll('.node-label').each(function (d) {
      const matchesSearch = !q || d.id.toLowerCase().includes(q) || (d.type || '').toLowerCase().includes(q)
      const matchesFilter = !filters.length || filters.includes(d.type)
      d3.select(this).attr('opacity', matchesSearch && matchesFilter ? 1 : 0.1)
    })
    sel.selectAll('line').each(function (d) {
      const srcId = d.source.id || d.source
      const tgtId = d.target.id || d.target
      const srcNode = graphData.nodes.find(n => n.id === srcId)
      const tgtNode = graphData.nodes.find(n => n.id === tgtId)
      const srcMatch = (!q || srcId.toLowerCase().includes(q)) && (!filters.length || filters.includes(srcNode?.type))
      const tgtMatch = (!q || tgtId.toLowerCase().includes(q)) && (!filters.length || filters.includes(tgtNode?.type))
      d3.select(this).attr('opacity', srcMatch || tgtMatch ? 1 : 0.05)
    })
  }

  function zoomIn() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.scaleBy, 1.4)
  }
  function zoomOut() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.scaleBy, 0.7)
  }
  function zoomReset() {
    if (_svgSelection.value && _zoomBehavior.value)
      _svgSelection.value.transition().duration(300).call(_zoomBehavior.value.transform, d3.zoomIdentity)
  }

  function panTo({ x, y }) {
    if (_svgSelection.value && _zoomBehavior.value) {
      _svgSelection.value.transition().duration(300).call(
        _zoomBehavior.value.transform,
        d3.zoomIdentity.translate(-x, -y)
      )
    }
  }

  function highlightNode(nodeId, className) {
    const container = _container.value
    if (!container) return
    d3.select(container)
      .selectAll('circle')
      .filter(d => d.id === nodeId)
      .classed(className, true)
  }

  function highlightPath(path) {
    const container = _container.value
    if (!container || !path.length) return
    clearHighlights()
    const pathSet = new Set(path)
    d3.select(container)
      .selectAll('circle')
      .filter(d => pathSet.has(d.id))
      .classed('in-path', true)
    d3.select(container)
      .selectAll('line')
      .filter(d => {
        const source = d.source.id || d.source
        const target = d.target.id || d.target
        return pathSet.has(source) && pathSet.has(target)
      })
      .classed('in-path', true)
  }

  function highlightNeighbors(centerId, neighbors) {
    const container = _container.value
    if (!container) return
    clearHighlights()
    d3.select(container)
      .selectAll('circle')
      .filter(d => d.id === centerId)
      .classed('neighbor-center', true)
    d3.select(container)
      .selectAll('circle')
      .filter(d => neighbors.has(d.id) && d.id !== centerId)
      .classed('neighbor-highlight', true)
  }

  function clearHighlights() {
    const container = _container.value
    if (!container) return
    d3.select(container)
      .selectAll('circle')
      .classed('path-start', false)
      .classed('path-end', false)
      .classed('in-path', false)
      .classed('neighbor-center', false)
      .classed('neighbor-highlight', false)
    d3.select(container)
      .selectAll('line')
      .classed('in-path', false)
  }

  // Lasso
  let _lassoPath = null
  let _lassoPoints = []
  let _isDrawingLasso = false

  function setupLasso(onComplete) {
    const container = _container.value
    if (!container) return
    const svg = d3.select(container).select('svg')
    if (svg.empty()) return

    svg.on('.lasso', null)
    svg
      .on('mousedown.lasso', (event) => {
        if (event.target.tagName !== 'circle') {
          _isDrawingLasso = true
          _lassoPoints = [[event.x, event.y]]
          _lassoPath = svg.append('path')
            .attr('class', 'lasso-selection')
            .attr('fill', 'rgba(0, 212, 255, 0.1)')
            .attr('stroke', '#00d4ff')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5, 5')
          _updateLassoPath()
        }
      })
      .on('mousemove.lasso', (event) => {
        if (_isDrawingLasso) {
          _lassoPoints.push([event.x, event.y])
          _updateLassoPath()
        }
      })
      .on('mouseup.lasso', () => {
        if (_isDrawingLasso) {
          _isDrawingLasso = false
          if (onComplete) onComplete(_lassoPoints)
          setTimeout(() => {
            if (_lassoPath) {
              _lassoPath.remove()
              _lassoPath = null
            }
            _lassoPoints = []
          }, 500)
        }
      })
  }

  function _updateLassoPath() {
    if (!_lassoPath || _lassoPoints.length < 2) return
    const pathString = _lassoPoints.map((p, i) =>
      i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`
    ).join(' ')
    _lassoPath.attr('d', pathString + ' Z')
  }

  function teardownLasso() {
    _isDrawingLasso = false
    if (_lassoPath) {
      _lassoPath.remove()
      _lassoPath = null
    }
    _lassoPoints = []
    const container = _container.value
    if (container) {
      d3.select(container).selectAll('circle').classed('lasso-selected', false)
    }
  }

  function stopSimulation() {
    _simulation.value?.stop()
  }

  function destroy() {
    _simulation.value?.stop()
    _hybridRenderer.value?.destroy()
    _resizeObserver?.disconnect()
    _resizeObserver = null
    _svgSelection.value = null
    _zoomBehavior.value = null
    _container.value = null
  }

  onScopeDispose(destroy)

  return {
    // Reactive reads
    viewport: readonly(viewport),
    connCounts: readonly(connCounts),
    isRendering: readonly(isRendering),
    renderMode: readonly(renderMode),

    // Lifecycle
    bind,
    destroy,

    // Actions
    render,
    applyLayout,
    applySearchFilters,
    stopSimulation,
    zoomIn, zoomOut, zoomReset, panTo,
    highlightNode, highlightPath, highlightNeighbors, clearHighlights,
    setupLasso, teardownLasso,
  }
}
