/**
 * Layout Transition Animation
 *
 * Provides smooth layout-to-layout transitions with D3.
 * Animates nodes and edges between layout states.
 *
 * @module utils/graph/rendering/transition
 */

import * as d3 from 'd3'
import { ANIMATION_CONFIG } from '@/constants/graph.js'

/**
 * Transition nodes to new positions
 *
 * @param {d3.Selection} nodeSelection - D3 selection of nodes
 * @param {Array} targetPositions - Array of {id, x, y} target positions
 * @param {number} duration - Transition duration in ms
 * @param {Function} callback - Optional callback on completion
 * @returns {d3.Transition} D3 transition object
 */
export function transitionNodes(nodeSelection, targetPositions, duration = ANIMATION_CONFIG.layoutTransition, callback = null) {
  // Create position map for O(1) lookup
  const positionMap = new Map(targetPositions.map(p => [p.id, p]))

  // Disable pointer events during transition
  nodeSelection
    .style('pointer-events', 'none')
    .style('cursor', 'wait')

  // Create transition
  const transition = nodeSelection.transition()
    .duration(duration)
    .ease(d3.easeCubicInOut)
    .attr('cx', function(d) {
      const pos = positionMap.get(d.id)
      return pos ? pos.x : d3.select(this).attr('cx')
    })
    .attr('cy', function(d) {
      const pos = positionMap.get(d.id)
      return pos ? pos.y : d3.select(this).attr('cy')
    })

  // Re-enable pointer events after transition
  transition
    .on('end', function() {
      d3.select(this)
        .style('pointer-events', null)
        .style('cursor', null)

      if (callback) callback()
    })

  return transition
}

/**
 * Transition node groups (for transform-based positioning)
 *
 * @param {d3.Selection} groupSelection - D3 selection of node groups
 * @param {Array} targetPositions - Array of {id, x, y} target positions
 * @param {number} duration - Transition duration in ms
 * @param {Function} callback - Optional callback on completion
 * @returns {d3.Transition} D3 transition object
 */
export function transitionNodeGroups(groupSelection, targetPositions, duration = ANIMATION_CONFIG.layoutTransition, callback = null) {
  const positionMap = new Map(targetPositions.map(p => [p.id, p]))

  groupSelection
    .style('pointer-events', 'none')
    .style('cursor', 'wait')

  const transition = groupSelection.transition()
    .duration(duration)
    .ease(d3.easeCubicInOut)
    .attr('transform', function(d) {
      const pos = positionMap.get(d.id)
      const x = pos ? pos.x : 0
      const y = pos ? pos.y : 0
      return `translate(${x}, ${y})`
    })

  transition
    .on('end', function() {
      d3.select(this)
        .style('pointer-events', null)
        .style('cursor', null)

      if (callback) callback()
    })

  return transition
}

/**
 * Transition edges to match node movements
 *
 * @param {d3.Selection} edgeSelection - D3 selection of edges
 * @param {Array} nodePositions - Array of {id, x, y} node positions
 * @param {number} duration - Transition duration in ms
 * @returns {d3.Transition} D3 transition object
 */
export function transitionEdges(edgeSelection, nodePositions, duration = ANIMATION_CONFIG.layoutTransition) {
  // Create position map for O(1) lookup
  const positionMap = new Map(nodePositions.map(p => [p.id, p]))

  return edgeSelection.transition()
    .duration(duration)
    .ease(d3.easeCubicInOut)
    .attr('x1', function(d) {
      const sourceId = d.source.id || d.source
      const pos = positionMap.get(sourceId)
      return pos ? pos.x : d3.select(this).attr('x1')
    })
    .attr('y1', function(d) {
      const sourceId = d.source.id || d.source
      const pos = positionMap.get(sourceId)
      return pos ? pos.y : d3.select(this).attr('y1')
    })
    .attr('x2', function(d) {
      const targetId = d.target.id || d.target
      const pos = positionMap.get(targetId)
      return pos ? pos.x : d3.select(this).attr('x2')
    })
    .attr('y2', function(d) {
      const targetId = d.target.id || d.target
      const pos = positionMap.get(targetId)
      return pos ? pos.y : d3.select(this).attr('y2')
    })
}

/**
 * Transition canvas edges (for hybrid rendering)
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {Array} edges - Array of edge objects
 * @param {Array} nodePositions - Array of {id, x, y} node positions
 * @param {number} progress - Animation progress (0-1)
 * @param {Function} drawEdge - Function to draw a single edge
 */
export function transitionCanvasEdges(ctx, edges, nodePositions, progress, drawEdge) {
  const positionMap = new Map(nodePositions.map(p => [p.id, p]))

  edges.forEach(edge => {
    const sourceId = edge.source.id || edge.source
    const targetId = edge.target.id || edge.target

    const sourcePos = positionMap.get(sourceId)
    const targetPos = positionMap.get(targetId)

    if (sourcePos && targetPos) {
      // Interpolate between current and target positions
      const currentSource = edge._currentSource || { x: sourcePos.x, y: sourcePos.y }
      const currentTarget = edge._currentTarget || { x: targetPos.x, y: targetPos.y }

      const x1 = currentSource.x + (sourcePos.x - currentSource.x) * progress
      const y1 = currentSource.y + (sourcePos.y - currentSource.y) * progress
      const x2 = currentTarget.x + (targetPos.x - currentTarget.x) * progress
      const y2 = currentTarget.y + (targetPos.y - currentTarget.y) * progress

      // Store current position for next frame
      if (progress < 1) {
        edge._currentSource = { x: x1, y: y1 }
        edge._currentTarget = { x: x2, y: y2 }
      }

      drawEdge(ctx, { x1, y1, x2, y2, ...edge })
    }
  })
}

/**
 * Calculate graph bounds during transition
 *
 * @param {Array} nodes - Array of node objects
 * @returns {Object} Bounds {minX, minY, maxX, maxY, width, height}
 */
export function calculateTransitionBounds(nodes) {
  if (!nodes.length) {
    return { minX: 0, minY: 0, maxX: 100, maxY: 100, width: 100, height: 100 }
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  nodes.forEach(node => {
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x)
    maxY = Math.max(maxY, node.y)
  })

  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
  }
}

/**
 * Animate layout transition with callback
 *
 * @param {Object} params - Transition parameters
 * @returns {d3.Transition} D3 transition object
 */
export function animateLayoutTransition(params) {
  const {
    nodeSelection,
    edgeSelection,
    targetPositions,
    duration = ANIMATION_CONFIG.layoutTransition,
    onComplete = null,
  } = params

  // Calculate bounds to maintain during transition
  const bounds = calculateTransitionBounds(targetPositions)

  // Run both transitions in parallel
  const nodeTransition = transitionNodes(nodeSelection, targetPositions, duration)
  const edgeTransition = transitionEdges(edgeSelection, targetPositions, duration)

  // Call completion callback when done
  if (onComplete) {
    nodeTransition.on('end', () => onComplete({ bounds }))
  }

  return { nodeTransition, edgeTransition, bounds }
}

/**
 * Create staggered node entry animation
 *
 * @param {d3.Selection} nodeSelection - D3 selection of nodes
 * @param {number} delay - Delay between each node
 * @param {number} duration - Animation duration per node
 * @returns {d3.Transition} D3 transition object
 */
export function animateNodeEntry(nodeSelection, delay = ANIMATION_CONFIG.nodeEntryDelay, duration = ANIMATION_CONFIG.nodeEntry) {
  return nodeSelection
    .attr('opacity', 0)
    .transition()
    .delay((d, i) => i * delay)
    .duration(duration)
    .ease(d3.easeCubicOut)
    .attr('opacity', 0.85)
}

/**
 * Create pulse animation for selected nodes
 *
 * @param {d3.Selection} nodeSelection - D3 selection of nodes
 * @returns {d3.Transition} D3 transition object
 */
export function animateNodePulse(nodeSelection) {
  return nodeSelection
    .transition()
    .duration(ANIMATION_CONFIG.pulse / 2)
    .ease(d3.easeSinInOut)
    .attr('opacity', 1)
    .attr('r', function() {
      return parseFloat(d3.select(this).attr('r')) * 1.2
    })
    .transition()
    .duration(ANIMATION_CONFIG.pulse / 2)
    .ease(d3.easeSinInOut)
    .attr('opacity', 0.85)
    .attr('r', function() {
      return parseFloat(d3.select(this).attr('r')) / 1.2
    })
    .on('end', function() {
      // Repeat infinitely
      animateNodePulse(d3.select(this))
    })
}

/**
 * Stop all active transitions on a selection
 *
 * @param {d3.Selection} selection - D3 selection
 */
export function stopTransitions(selection) {
  selection.interrupt()
}

/**
 * Check if a transition is active
 *
 * @param {d3.Selection} selection - D3 selection
 * @returns {boolean} True if transition is active
 */
export function isTransitionActive(selection) {
  return !selection.empty() && selection.node().__transition
}
