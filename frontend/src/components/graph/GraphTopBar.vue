<!--
GraphTopBar Component

Top navigation bar for the graph visualization.
Contains search input, entity type filter buttons, and settings toggle.

@emits update:searchQuery - Emitted when search input changes
@emits toggle-filter - Emitted when a filter button is clicked
@emits toggle-settings - Emitted when settings button is clicked
-->

<script setup>
import { Settings } from 'lucide-vue-next'
import { Search } from 'lucide-vue-next'

const props = defineProps({
  searchQuery: {
    type: String,
    default: '',
  },
  entityTypes: {
    type: Array,
    default: () => [],
    validator: (value) => value.every(item => typeof item === 'string'),
  },
  activeFilters: {
    type: Array,
    default: () => [],
  },
  settingsPanelOpen: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:searchQuery',
  'toggle-filter',
  'toggle-settings',
])

function handleSearchInput(event) {
  emit('update:searchQuery', event.target.value)
}

function handleFilterToggle(type) {
  emit('toggle-filter', type)
}

function handleSettingsToggle() {
  emit('toggle-settings')
}
</script>

<template>
  <div class="graph-top-bar">
    <div class="search-section">
      <Search :size="14" />
      <input
        id="entity-search"
        :value="searchQuery"
        @input="handleSearchInput"
        placeholder="Search entities..."
        aria-label="Search entities"
      />
    </div>
    <div v-if="entityTypes.length > 0" class="filter-section">
      <button
        v-for="(type, index) in entityTypes"
        :key="type"
        :class="{ active: activeFilters.includes(type) }"
        :style="{ animationDelay: `${index * var(--filter-stagger-delay, 25)}ms` }"
        :aria-pressed="activeFilters.includes(type)"
        @click="handleFilterToggle(type)"
      >
        {{ type }}
      </button>
    </div>
    <button
      class="settings-toggle"
      :class="{ active: settingsPanelOpen }"
      :aria-pressed="settingsPanelOpen"
      aria-label="Toggle settings panel"
      @click="handleSettingsToggle"
    >
      <Settings :size="16" />
    </button>
  </div>
</template>

<style scoped>
.graph-top-bar {
  --filter-stagger-delay: 25ms;
  --filter-animation-duration: 300ms;

  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  height: 53px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: -0.01em;
}

.search-section {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-sunken);
  border-radius: 8px;
  padding: 6px 12px;
  border: 1px solid transparent;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 0;
}

.search-section:focus-within {
  border-color: var(--color-primary, rgba(0, 212, 255, 0.3));
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

.search-section input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
}

.search-section input::placeholder {
  color: var(--text-tertiary);
}

.filter-section {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.filter-section button {
  padding: 6px 12px;
  border-radius: 6px;
  background: var(--surface-sunken);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  border: 1px solid transparent;
  white-space: nowrap;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  animation: filter-enter var(--filter-animation-duration, 300ms) ease-out forwards;
  opacity: 0;
}

@keyframes filter-enter {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.filter-section button:hover {
  background: var(--surface-elevated);
  transform: translateY(-1px);
  border-color: var(--border);
}

.filter-section button.active {
  background: var(--color-primary, #00d4ff);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 212, 255, 0.3);
  border-color: var(--color-primary);
  opacity: 1;
}

.settings-toggle {
  padding: 8px;
  border-radius: 8px;
  background: var(--surface-sunken);
  border: none;
  cursor: pointer;
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-toggle:hover {
  background: var(--surface-elevated);
  transform: scale(1.05);
}

.settings-toggle.active {
  background: var(--color-primary, #00d4ff);
  color: white;
  box-shadow: 0 2px 12px rgba(0, 212, 255, 0.4);
}

.settings-toggle.active svg {
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

/* Keyboard focus indicators */
.filter-section button:focus-visible,
.settings-toggle:focus-visible {
  outline: 2px solid var(--color-primary, #00d4ff);
  outline-offset: 2px;
}

/* Responsive */
@media (max-width: 767px) {
  .graph-top-bar {
    flex-wrap: wrap;
    padding: 8px;
  }

  .search-section {
    width: 100%;
    order: 1;
  }

  .filter-section {
    width: 100%;
    order: 2;
    overflow-x: auto;
  }

  .settings-toggle {
    position: absolute;
    top: 8px;
    right: 8px;
    order: 3;
  }
}
</style>
