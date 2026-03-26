<!--
     GraphStatsPanel Component

     Displays quick metrics about the current graph state.
     Shows node count, edge count, cluster count, selected count, and layout.

     No emits - read-only display component.
     -->

<script setup>
import { computed } from 'vue'
import { BarChart3, Link, Package, Check, Settings, TrendingUp } from 'lucide-vue-next'

// Props
const props = defineProps({
  nodeCount: {
    type: Number,
    default: 0,
  },
  edgeCount: {
    type: Number,
    default: 0,
  },
  clusterCount: {
    type: Number,
    default: 0,
  },
  selectedCount: {
    type: Number,
    default: 0,
  },
  layout: {
    type: String,
    default: 'force',
  },
})

// Format large numbers for display
const formatNumber = (num) => {
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`
  }
  return num.toString()
}

// Compute average connections per node
const avgConnections = computed(() => {
  if (props.nodeCount === 0) return 0
  return (props.edgeCount * 2 / props.nodeCount).toFixed(1)
})
</script>

<template>
  <div class="graph-stats">
    <!-- Primary stats row -->
    <div class="stats-row">
      <div class="stat primary">
        <BarChart3 :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(props.nodeCount) }}</span>
          <span class="stat-label">Nodes</span>
        </div>
      </div>

      <div class="stat primary">
        <Link :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(props.edgeCount) }}</span>
          <span class="stat-label">Edges</span>
        </div>
      </div>
    </div>

    <!-- Secondary stats row -->
    <div class="stats-row">
      <div
        v-if="props.clusterCount > 0"
        class="stat secondary"
      >
        <Package :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ props.clusterCount }}</span>
          <span class="stat-label">Clusters</span>
        </div>
      </div>

      <div
        v-if="props.selectedCount > 0"
        class="stat secondary highlight"
      >
        <Check :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ props.selectedCount }}</span>
          <span class="stat-label">Selected</span>
        </div>
      </div>

      <div class="stat secondary">
        <Settings :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ props.layout }}</span>
          <span class="stat-label">Layout</span>
        </div>
      </div>

      <div class="stat secondary" title="Average connections per node">
        <TrendingUp :size="14" class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ avgConnections }}</span>
          <span class="stat-label">Avg Conn</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--surface-raised);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-md);
}

.stats-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  transition: all 150ms ease-out;
}

.stat:hover {
  background: var(--surface-elevated);
  border-color: var(--border);
}

.stat.primary {
  flex: 1;
  min-width: 80px;
}

.stat.secondary {
  flex: 0;
}

.stat.highlight {
  background: var(--accent-surface);
  border-color: var(--color-primary);
}

.stat-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  line-height: 1.2;
  transition: color 150ms ease-out;
}

.stat.highlight .stat-value {
  color: var(--color-primary);
}

.stat-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  color: var(--text-tertiary);
}

@media (max-width: 640px) {
  .graph-stats { padding: 10px 12px; }
  .stats-row { gap: 8px; }
  .stat { padding: 6px 10px; }
  .stat-value { font-size: 14px; }
}
</style>
