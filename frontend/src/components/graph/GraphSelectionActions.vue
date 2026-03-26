<!--
GraphSelectionActions Component

Action buttons for multi-select operations.
Appears when nodes are selected, provides bulk actions.

@emits action - Emitted when an action is triggered
-->

<script setup>
import { computed } from 'vue'
import { X, Check, RotateCcw, Download } from 'lucide-vue-next'

const props = defineProps({
  selectedNodes: {
    type: Array,
    default: () => [],
  },
  totalNodes: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['action'])

const hasSelection = computed(() => props.selectedNodes.length > 0)

const actions = computed(() => [
  {
    id: 'deselect',
    label: 'Deselect',
    icon: X,
    disabled: !hasSelection.value,
    variant: 'secondary',
  },
  {
    id: 'selectAll',
    label: 'Select All',
    icon: Check,
    disabled: props.selectedNodes.length >= props.totalNodes,
    variant: 'secondary',
  },
  {
    id: 'invert',
    label: 'Invert',
    icon: RotateCcw,
    disabled: props.totalNodes === 0,
    variant: 'secondary',
  },
  {
    id: 'export',
    label: 'Export',
    icon: Download,
    disabled: !hasSelection.value,
    variant: 'primary',
  },
])

function handleAction(actionId) {
  emit('action', actionId)
}
</script>

<template>
  <div class="selection-actions">
    <div class="actions-header">
      <span class="actions-count">{{ selectedNodes.length }} selected</span>
      <span v-if="totalNodes > 0" class="actions-total">of {{ totalNodes }}</span>
    </div>

    <div class="actions-list">
      <button
        v-for="action in actions"
        :key="action.id"
        :disabled="action.disabled"
        :class="['action-button', `action-${action.variant}`]"
        @click="handleAction(action.id)"
        :title="action.label"
      >
        <component :is="action.icon" :size="14" />
        <span>{{ action.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.selection-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--surface-raised);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.actions-header {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.actions-count {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-primary);
}

.actions-total {
  font-size: 11px;
  color: var(--text-secondary);
}

.actions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all 150ms ease-out;
}

.action-button:hover:not(:disabled) {
  background: var(--surface-hover, var(--surface-raised));
  border-color: var(--border);
  transform: translateY(-1px);
}

.action-button:active:not(:disabled) {
  transform: translateY(0);
}

.action-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.action-primary {
  background: transparent;
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.action-primary:hover:not(:disabled) {
  background: var(--surface-raised);
  border-color: var(--color-primary);
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.2);
}
</style>
