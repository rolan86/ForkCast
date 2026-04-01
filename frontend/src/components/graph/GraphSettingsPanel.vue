<!--
GraphSettingsPanel Component

Slide-out settings panel for graph controls.
Contains layout selection, visual options, and advanced settings.

@emits close - Emitted when user closes panel
@emits select-layout - Emitted when user selects a layout
@emits toggle-visual-mode - Emitted when user toggles 2.5D mode
@emits toggle-performance-mode - Emitted when user toggles performance mode
@emits select-render-mode - Emitted when user selects render mode
@emits select-interaction-mode - Emitted when user selects interaction mode
@emits toggle-stats - Emitted when user toggles stats panel visibility
@emits toggle-mini-map - Emitted when user toggles mini-map visibility
@emits toggle-clustering - Emitted when user toggles auto-clustering
-->

<script setup>
import { ref, computed } from 'vue'
import { X, ChevronRight } from 'lucide-vue-next'
import { LAYOUT_TYPES, RENDER_MODES, INTERACTION_MODES, VISUAL_MODES } from '@/constants/graph.js'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false,
  },
  currentLayout: {
    type: String,
    default: LAYOUT_TYPES.FORCE,
    validator: (value) => Object.values(LAYOUT_TYPES).includes(value),
  },
  visualMode: {
    type: String,
    default: VISUAL_MODES.TWO_POINT_FIVE_D,
  },
  performanceMode: {
    type: Boolean,
    default: false,
  },
  renderMode: {
    type: String,
    default: RENDER_MODES.HYBRID,
    validator: (value) => Object.values(RENDER_MODES).includes(value),
  },
  interactionMode: {
    type: String,
    default: INTERACTION_MODES.SELECT,
    validator: (value) => Object.values(INTERACTION_MODES).includes(value),
  },
  showStats: {
    type: Boolean,
    default: false,
  },
  showMiniMap: {
    type: Boolean,
    default: false,
  },
  clusteringEnabled: {
    type: Boolean,
    default: false,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  connectionStyle3d: {
    type: String,
    default: 'curved',
  },
  glowEnabled3d: {
    type: Boolean,
    default: true,
  },
  pulseEnabled3d: {
    type: Boolean,
    default: true,
  },
  autoRotate3d: {
    type: Boolean,
    default: false,
  },
  performancePreset3d: {
    type: String,
    default: 'quality',
  },
})

const emit = defineEmits([
  'close',
  'select-layout',
  'toggle-visual-mode',
  'toggle-performance-mode',
  'select-render-mode',
  'select-interaction-mode',
  'toggle-stats',
  'toggle-mini-map',
  'toggle-clustering',
  'update-3d-settings',
  'apply-performance-preset',
])

// Accordion state
const advancedExpanded = ref(false)

function toggleAdvanced() {
  advancedExpanded.value = !advancedExpanded.value
}

// Layout options
const layoutOptions = computed(() => [
  { value: LAYOUT_TYPES.FORCE, label: 'Force' },
  { value: LAYOUT_TYPES.HIERARCHICAL, label: 'Hierarchy' },
  { value: LAYOUT_TYPES.CIRCULAR, label: 'Circular' },
  { value: LAYOUT_TYPES.CLUSTERED, label: 'Clustered' },
])

// Render mode options
const renderModeOptions = computed(() => [
  { value: RENDER_MODES.SVG, label: 'SVG' },
  { value: RENDER_MODES.HYBRID, label: 'Hybrid' },
  { value: RENDER_MODES.CANVAS, label: 'Canvas' },
])

// Interaction mode options
const interactionModeOptions = computed(() => [
  { value: INTERACTION_MODES.SELECT, label: 'Select' },
  { value: INTERACTION_MODES.PATH, label: 'Path' },
  { value: INTERACTION_MODES.NEIGHBOR, label: 'Neighbor' },
  { value: INTERACTION_MODES.LASSO, label: 'Lasso' },
])
</script>

<template>
  <Transition name="slide-in-right">
    <div v-if="isOpen" class="settings-panel">
      <!-- Close button -->
      <button class="settings-close" aria-label="Close settings" @click="$emit('close')">
        <X :size="16" />
      </button>

      <!-- Loading indicator -->
      <div v-if="isLoading" class="settings-loading">
        <div class="loading-spinner" />
        <span class="loading-text">Applying layout...</span>
      </div>

      <!-- Layout Section -->
      <div class="settings-section">
        <div class="settings-header">Layout</div>
        <div class="layout-radios">
          <label
            v-for="option in layoutOptions"
            :key="option.value"
            :class="['layout-radio', { selected: currentLayout === option.value }]"
          >
            <input
              type="radio"
              name="layout"
              :value="option.value"
              :checked="currentLayout === option.value"
              :disabled="isLoading"
              @change="$emit('select-layout', option.value)"
            />
            <span>{{ option.label }}</span>
          </label>
        </div>
      </div>

      <!-- Visual Options Section -->
      <div class="settings-section">
        <div class="settings-header">Visual Options</div>

        <div class="setting-row">
          <label class="setting-label">Visual Mode</label>
          <select
            class="setting-select"
            :value="visualMode"
            @change="$emit('toggle-visual-mode', $event.target.value)"
          >
            <option :value="VISUAL_MODES.TWO_D">2D Flat</option>
            <option :value="VISUAL_MODES.TWO_POINT_FIVE_D">2.5D Holographic</option>
            <option :value="VISUAL_MODES.THREE_D">3D Brain</option>
          </select>
        </div>

        <label class="option-checkbox">
          <input
            type="checkbox"
            :checked="performanceMode"
            @change="$emit('toggle-performance-mode', $event.target.checked)"
          />
          <span>Performance mode (no animations)</span>
        </label>
      </div>

      <!-- 3D Settings Section -->
      <div class="settings-section" v-if="visualMode === '3d'">
        <div class="settings-header">3D Settings</div>

        <!-- Connection Style -->
        <div class="setting-row">
          <label class="setting-label">Connection Style</label>
          <select
            data-testid="connection-style-select"
            class="setting-select"
            :value="connectionStyle3d"
            @change="$emit('update-3d-settings', { connectionStyle: $event.target.value })"
          >
            <option value="curved">Curved Paths</option>
            <option value="particle">Particle Flow — GPU heavy</option>
            <option value="adaptive">Adaptive — Auto-optimizes</option>
          </select>
        </div>

        <!-- Glow Toggle -->
        <label class="option-checkbox">
          <input
            type="checkbox"
            :checked="glowEnabled3d"
            @change="$emit('update-3d-settings', { glowEnabled: $event.target.checked })"
          />
          <span>Node Glow</span>
        </label>

        <!-- Pulse Toggle -->
        <label class="option-checkbox">
          <input
            type="checkbox"
            :checked="pulseEnabled3d"
            @change="$emit('update-3d-settings', { pulseEnabled: $event.target.checked })"
          />
          <span>Node Pulse</span>
          <span class="setting-hint">Moderate GPU</span>
        </label>

        <!-- Auto-Rotate Toggle -->
        <label class="option-checkbox">
          <input
            type="checkbox"
            :checked="autoRotate3d"
            @change="$emit('update-3d-settings', { autoRotate: $event.target.checked })"
          />
          <span>Auto-Rotate</span>
        </label>

        <!-- Performance Presets -->
        <div class="settings-header" style="margin-top: 12px;">Performance</div>
        <div class="preset-buttons">
          <button
            data-testid="preset-quality"
            class="preset-btn"
            :class="{ active: performancePreset3d === 'quality' }"
            @click="$emit('apply-performance-preset', 'quality')"
          >Quality</button>
          <button
            data-testid="preset-balanced"
            class="preset-btn"
            :class="{ active: performancePreset3d === 'balanced' }"
            @click="$emit('apply-performance-preset', 'balanced')"
          >Balanced</button>
          <button
            data-testid="preset-performance"
            class="preset-btn"
            :class="{ active: performancePreset3d === 'performance' }"
            @click="$emit('apply-performance-preset', 'performance')"
          >Performance</button>
        </div>
      </div>

      <!-- Advanced Section -->
      <div class="settings-section">
        <button
          class="accordion-trigger"
          aria-label="Toggle advanced settings"
          :aria-expanded="advancedExpanded"
          @click="toggleAdvanced"
        >
          <span class="settings-header">Advanced</span>
          <ChevronRight
            :size="14"
            :class="['accordion-chevron', { open: advancedExpanded }]"
          />
        </button>

        <div :class="['accordion-content', { expanded: advancedExpanded }]">
          <div class="accordion-inner">
            <label class="option-checkbox">
              <input
                type="checkbox"
                :checked="showStats"
                @change="$emit('toggle-stats', $event.target.checked)"
              />
              <span>Show stats panel</span>
            </label>

            <label class="option-checkbox">
              <input
                type="checkbox"
                :checked="showMiniMap"
                @change="$emit('toggle-mini-map', $event.target.checked)"
              />
              <span>Show mini-map</span>
            </label>

            <div class="select-group">
              <label class="select-label">Render</label>
              <select
                :value="renderMode"
                :disabled="isLoading"
                @change="$emit('select-render-mode', $event.target.value)"
                class="select-input"
              >
                <option
                  v-for="option in renderModeOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div class="select-group">
              <label class="select-label">Mode</label>
              <select
                :value="interactionMode"
                :disabled="isLoading"
                @change="$emit('select-interaction-mode', $event.target.value)"
                class="select-input"
              >
                <option
                  v-for="option in interactionModeOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>

            <label class="option-checkbox">
              <input
                type="checkbox"
                :checked="clusteringEnabled"
                @change="$emit('toggle-clustering', $event.target.checked)"
              />
              <span>Auto-clustering</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.settings-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 300px;
  background: var(--surface-raised);
  border-left: 1px solid var(--border);
  box-shadow:
    -4px 0 24px rgba(0, 0, 0, 0.15),
    -1px 0 8px rgba(0, 0, 0, 0.1),
    inset 1px 0 0 rgba(255, 255, 255, 0.05);
  overflow-y: auto;
  z-index: 50;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
}

.settings-close {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 8px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all 150ms;
}

.settings-close:hover {
  background: var(--surface-sunken);
  color: var(--text-secondary);
}

.settings-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(0, 212, 255, 0.1);
  border-radius: 6px;
  margin: 12px 20px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 600ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 500;
}

.settings-section {
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

.settings-section:last-child {
  border-bottom: none;
}

.settings-header {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

.layout-radios {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.layout-radio {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 13px;
  font-weight: 500;
}

.layout-radio:hover {
  background: var(--surface-elevated);
  border-color: var(--border);
}

.layout-radio.selected {
  background: rgba(0, 212, 255, 0.15);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.layout-radio:has(:disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}

.layout-radio input[type="radio"] {
  appearance: none;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
  transition: all 150ms;
}

.layout-radio input[type="radio"]:checked {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.option-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: color 150ms;
}

.option-checkbox:hover {
  color: var(--text-primary);
}

.option-checkbox input[type="checkbox"] {
  appearance: none;
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-radius: 4px;
  flex-shrink: 0;
  transition: all 150ms;
  position: relative;
}

.option-checkbox input[type="checkbox"]:checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.option-checkbox input[type="checkbox"]:checked::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-size: 12px;
  font-weight: bold;
}

.accordion-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 0;
  cursor: pointer;
  user-select: none;
  background: transparent;
  border: none;
}

.accordion-content {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.accordion-content.expanded {
  grid-template-rows: 1fr;
}

.accordion-inner {
  overflow: hidden;
}

.accordion-chevron {
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.accordion-chevron.open {
  transform: rotate(90deg);
}

.select-group {
  margin: 12px 0;
}

.select-label {
  display: block;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.select-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}

/* Keyboard focus indicators */
.settings-close:focus-visible,
.accordion-trigger:focus-visible,
.layout-radio:focus-visible,
.option-checkbox:focus-visible,
.select-input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Slide animation */
.slide-in-right-enter-active .settings-panel {
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-in-right-leave-active .settings-panel {
  transition: transform 200ms cubic-bezier(0.4, 0, 1, 1);
}

.slide-in-right-enter-from .settings-panel {
  transform: translateX(100%);
}

.slide-in-right-leave-to .settings-panel {
  transform: translateX(100%);
}

.setting-row {
  margin: 8px 0;
}

.setting-label {
  display: block;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.setting-select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}

.preset-buttons {
  display: flex;
  gap: 6px;
}

.preset-btn {
  flex: 1;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 150ms;
}

.preset-btn:hover {
  background: var(--surface-elevated);
  color: var(--text-primary);
}

.preset-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.setting-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

/* Responsive */
@media (max-width: 767px) {
  .settings-panel {
    width: 85%;
  }
}
</style>
