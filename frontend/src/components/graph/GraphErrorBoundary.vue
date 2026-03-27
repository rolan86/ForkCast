<!--
GraphErrorBoundary Component

Catches and handles rendering errors in the graph visualization.
Provides a graceful degradation UI with retry functionality.

Uses Vue 3's onErrorCaptured lifecycle hook to catch errors
from child components.
-->

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { AlertTriangle, RefreshCw, X } from 'lucide-vue-next'

// State
const hasError = ref(false)
const errorMessage = ref('')
const errorStack = ref('')

// Emit
const emit = defineEmits(['reset'])

/**
 * Capture errors from child components
 * Returns false to prevent error from propagating further
 */
onErrorCaptured((err, instance, info) => {
  console.error('[GraphErrorBoundary] Captured error:', err)
  console.error('[GraphErrorBoundary] Component info:', info)
  console.error('[GraphErrorBoundary] Instance:', instance)

  hasError.value = true
  errorMessage.value = err.message || 'An unexpected error occurred while rendering the graph'
  errorStack.value = err.stack || ''

  // Prevent error from propagating
  return false
})

/**
 * Retry rendering the graph
 */
function retry() {
  hasError.value = false
  errorMessage.value = ''
  errorStack.value = ''
}

/**
 * Reset the graph and emit reset event
 */
function reset() {
  retry()
  emit('reset')
}

/**
 * Copy error details for debugging
 */
function copyErrorDetails() {
  const details = `Error: ${errorMessage.value}\n\nStack:\n${errorStack.value}`
  navigator.clipboard.writeText(details).then(() => {
    // Could add a toast notification here
    console.log('Error details copied to clipboard')
  }).catch(err => {
    console.error('Failed to copy error details:', err)
  })
}
</script>

<template>
  <!-- Show child content when no error -->
  <slot v-if="!hasError" />

  <!-- Error state display -->
  <div
    v-else
    class="error-boundary-state"
    :style="{
      background: 'var(--surface-raised)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
    }"
  >
    <div class="error-content">
      <!-- Error icon -->
      <div class="error-icon">
        <AlertTriangle :size="32" />
      </div>

      <!-- Error message -->
      <h3 class="error-title">Graph Display Error</h3>
      <p class="error-message">{{ errorMessage }}</p>

      <!-- Error stack trace (collapsible, for debugging) -->
      <details
        v-if="errorStack"
        class="error-details"
      >
        <summary>Technical details</summary>
        <pre class="error-stack">{{ errorStack }}</pre>
        <button
          @click="copyErrorDetails"
          class="copy-button"
        >
          Copy Error Details
        </button>
      </details>

      <!-- Action buttons -->
      <div class="error-actions">
        <button
          @click="retry"
          class="action-button primary"
        >
          <RefreshCw :size="16" />
          Retry
        </button>
        <button
          @click="reset"
          class="action-button secondary"
        >
          Reset Graph
        </button>
      </div>

      <!-- Helpful hints -->
      <div class="error-hints">
        <p class="hint-title">This might be caused by:</p>
        <ul class="hint-list">
          <li>Large graph size (try reducing the data)</li>
          <li>Browser memory limits</li>
          <li>Invalid graph data structure</li>
          <li>Browser compatibility issues</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-boundary-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 32px;
  margin: 16px;
}

.error-content {
  max-width: 480px;
  text-align: center;
}

.error-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  margin-bottom: 16px;
}

.error-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.error-message {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 24px 0;
  line-height: 1.5;
}

.error-details {
  text-align: left;
  margin: 16px 0;
  padding: 16px;
  background: var(--surface-sunken);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.error-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  user-select: none;
}

.error-details summary:hover {
  color: var(--text-primary);
}

.error-stack {
  margin-top: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  font-size: 11px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  color: var(--text-tertiary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.copy-button {
  margin-top: 12px;
  padding: 6px 12px;
  font-size: 12px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 150ms ease-out;
}

.copy-button:hover {
  background: var(--surface-raised);
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.action-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 150ms ease-out;
}

.action-button.primary {
  background: var(--accent-primary);
  color: white;
  border: none;
}

.action-button.primary:hover {
  background: var(--accent-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 212, 255, 0.3);
}

.action-button.secondary {
  background: var(--surface-sunken);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.action-button.secondary:hover {
  background: var(--surface-elevated);
  border-color: var(--text-tertiary);
}

.error-hints {
  text-align: left;
  padding: 16px;
  background: rgba(59, 130, 246, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.hint-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 8px 0;
}

.hint-list {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
  padding-left: 20px;
}

.hint-list li {
  margin-bottom: 4px;
}
</style>
