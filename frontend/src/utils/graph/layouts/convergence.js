/**
 * Convergence utilities for adaptive force layout
 *
 * Energy-based convergence detection with RK45-inspired adaptive
 * alpha decay. Pure functions — no side effects, no D3 dependency.
 *
 * @module utils/graph/layouts/convergence
 */

/**
 * Compute per-node kinetic energy.
 * Normalizing by node count ensures the threshold works consistently
 * across graph sizes.
 *
 * @param {Array} nodes - D3 simulation nodes with vx, vy
 * @returns {number} Average kinetic energy per node (0 for empty array)
 */
export function computeKineticEnergy(nodes) {
  const n = nodes.length
  if (n === 0) return 0

  let total = 0
  for (let i = 0; i < n; i++) {
    const vx = nodes[i].vx || 0
    const vy = nodes[i].vy || 0
    total += vx * vx + vy * vy
  }
  return total / n
}

/**
 * Check if force layout has converged.
 *
 * @param {number} energy - Current per-node kinetic energy
 * @param {number} threshold - Energy below which layout is settled
 * @param {number} iteration - Current iteration index (0-based)
 * @param {number} maxIteration - Maximum iteration index (inclusive)
 * @returns {boolean} True if layout should stop
 */
export function hasConverged(energy, threshold, iteration, maxIteration) {
  return energy <= threshold || iteration >= maxIteration
}

/**
 * Adapt alpha decay based on signed energy change rate.
 *
 * Positive energyDelta = energy decreasing (converging) → cool faster
 * Negative energyDelta = energy increasing (oscillating) → cool slower
 * Near-zero energyDelta = equilibrium → cool faster (nearly done)
 *
 * @param {number} currentDecay - Current alphaDecay value
 * @param {number} energyDelta - Signed relative change: (prevE - E) / prevE
 * @param {Object} bounds - { min, max, adaptRate }
 * @returns {number} New alphaDecay value, clamped to [min, max]
 */
export function adaptAlphaDecay(currentDecay, energyDelta, bounds) {
  const { min, max, adaptRate } = bounds

  let newDecay
  if (energyDelta < -0.01) {
    // Oscillating: energy increasing, slow down cooling
    newDecay = currentDecay * (1 - adaptRate)
  } else {
    // Converging or near-equilibrium: speed up cooling
    newDecay = currentDecay * (1 + adaptRate)
  }

  return Math.max(min, Math.min(max, newDecay))
}
