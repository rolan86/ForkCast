/**
 * Graph visualization constants
 *
 * Contains color palettes, render modes, layout configurations,
 * and visual style constants for the graph UI.
 */

/**
 * Neon color palette for 2.5D holographic effect
 * Each entity type gets a distinct neon color with bright, saturated values
 */
export const NEON_COLORS = {
  Person: '#00d4ff',      // cyan neon
  Organization: '#a855f7', // purple neon
  Concept: '#818cf8',     // indigo neon
  Topic: '#34d399',       // green neon
  Event: '#fbbf24',       // amber neon
  Location: '#f87171',    // red neon
  Product: '#f472b6',     // pink neon
}

/**
 * Glow intensity levels for different interaction states
 * Used to calculate opacity and shadow blur radius
 */
export const GLOW_INTENSITY = {
  default: 0.6,   // Base glow for normal nodes
  hover: 1.0,      // Increased glow on hover
  selected: 1.5,   // Maximum glow for selected nodes
}

/**
 * Render modes for graph visualization
 * Auto-switched based on node count for optimal performance
 */
export const RENDER_MODES = {
  SVG: 'svg',           // Pure SVG rendering for <100 nodes
  CANVAS: 'canvas',     // Pure canvas rendering for 300+ nodes
  HYBRID: 'hybrid',     // Canvas edges + SVG nodes for 100-300 nodes
}

/**
 * Layout algorithm identifiers
 */
export const LAYOUT_TYPES = {
  FORCE: 'force',
  HIERARCHICAL: 'hierarchical',
  CIRCULAR: 'circular',
  CLUSTERED: 'clustered',
}

/**
 * Force layout configuration
 * Default parameters for D3 force simulation
 */
export const FORCE_LAYOUT_CONFIG = {
  linkDistance: 80,      // Target distance between connected nodes
  chargeStrength: -200,  // Repulsion force (negative = repel)
  collideRadius: 8,      // Minimum distance between node boundaries
  alphaDecay: 0.02,      // Simulation cooling rate
  velocityDecay: 0.4,    // Velocity damping
}

/**
 * Hierarchical layout configuration
 * Default parameters for tree-based layout
 */
export const HIERARCHICAL_LAYOUT_CONFIG = {
  nodeWidth: 120,        // Width reserved for each node
  nodeHeight: 50,        // Height reserved for each node
  levelSpacing: 80,      // Vertical spacing between levels
  siblingSpacing: 30,    // Horizontal spacing between siblings
  maxRoots: 3,           // Maximum number of root nodes to use
}

/**
 * Circular layout configuration
 * Default parameters for circular arrangement
 */
export const CIRCULAR_LAYOUT_CONFIG = {
  radius: 300,           // Base radius for circular layout
  wedgePadding: 0.05,    // Padding between type wedges (radians)
  nodeSize: 20,          // Reserved space for each node on circle
}

/**
 * Clustered layout configuration
 * Default parameters for community-based layout
 */
export const CLUSTERED_LAYOUT_CONFIG = {
  minClusterSize: 3,     // Minimum nodes to form a cluster
  maxClusters: 15,       // Maximum number of clusters to detect
  clusterPadding: 20,    // Padding around cluster boundaries
  interClusterDistance: 150, // Target distance between cluster centers
}

/**
 * Visual mode identifiers
 */
export const VISUAL_MODES = {
  TWO_D: '2d',       // Flat rendering
  TWO_POINT_FIVE_D: '2.5d',  // 2.5D holographic effect with depth and glow
  THREE_D: '3d',     // Full 3D rendering with three.js
}

/**
 * Interaction mode identifiers
 */
export const INTERACTION_MODES = {
  SELECT: 'select',     // Single/multi-select nodes
  PATH: 'path',         // Find shortest path between two nodes
  NEIGHBOR: 'neighbor', // Highlight N-hop neighbors
  LASSO: 'lasso',       // Drag to select multiple nodes
}

/**
 * Performance thresholds for render mode switching
 */
export const PERFORMANCE_THRESHOLDS = {
  svgMaxNodes: 100,      // Switch to hybrid at 100 nodes
  hybridMaxNodes: 300,   // Switch to canvas at 300 nodes
  targetFPS: 30,         // Minimum acceptable frame rate
  maxConcurrentAnimations: 20,
  maxEdgePulses: 5,
}

/**
 * Animation configuration
 */
export const ANIMATION_CONFIG = {
  layoutTransition: 500,    // Layout transition duration (ms)
  nodeEntry: 200,           // Node entry animation (ms)
  nodeEntryDelay: 20,       // Delay between node entries (ms)
  hover: 150,               // Hover state transition (ms)
  pulse: 2000,              // Pulse animation duration (ms) - infinite loop
  clusterCollapse: 300,     // Cluster collapse animation (ms)
  clusterExpand: 300,       // Cluster expand animation (ms)
}

/**
 * 3D render configuration
 * Camera, geometry, and animation defaults for three.js 3D graphs
 */
export const RENDER_CONFIG_3D = {
  cameraFOV: 60,
  cameraDistance: 150,
  maxCameraDistance: 500,
  minCameraDistance: 50,
  orbitDamping: 0.05,
  autoRotateSpeed: 0.5,
  diveInDistance: 30,
  diveInDuration: 800,
  idleAutoRotateDelay: 10000,
  pulseFrequency: 0.5,
  pulseAmplitude: 0.05,
  nodeBaseRadius: 2,
  nodeMaxRadius: 8,
  sphereSegments: 32,
  icosahedronDetail: 1,
  sphereNodeThreshold: 300,
  pulseDisableThreshold: 500,
  fpsLowThreshold: 20,
  fpsLowDuration: 3000,
  fpsToastCooldown: 60000,
}

/**
 * Connection style identifiers for 3D graphs
 */
export const CONNECTION_STYLES = {
  CURVED: 'curved',
  PARTICLE: 'particle',
  ADAPTIVE: 'adaptive',
  NEURON: 'neuron',
}

/**
 * Camera distance thresholds for adaptive connection styles
 */
export const ADAPTIVE_THRESHOLDS = {
  overviewDistance: 500,
  midRangeDistance: 200,
  closeUpDistance: 50,
}

/**
 * Performance presets for 3D rendering
 * Trade-offs between visual quality and frame rate
 */
export const PERFORMANCE_PRESETS = {
  QUALITY: {
    glow: true,
    pulse: true,
    connectionStyle: 'curved',
    geometryDetail: 'high',
  },
  BALANCED: {
    glow: true,
    pulse: false,
    connectionStyle: 'adaptive',
    geometryDetail: 'high',
  },
  PERFORMANCE: {
    glow: false,
    pulse: false,
    connectionStyle: 'curved',
    geometryDetail: 'low',
  },
}
