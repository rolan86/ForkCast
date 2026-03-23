<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import StepIndicator from './StepIndicator.vue'

const props = defineProps({
  title: { type: String, required: true },
  steps: { type: Array, required: true },
  currentStage: { type: String, default: '' },
  progress: { type: Object, default: () => ({ current: null, total: null }) },
  logEntries: { type: Array, default: () => [] },
  error: { type: String, default: '' },
  disconnected: { type: Boolean, default: false },
  errorType: { type: String, default: '' },
  resumable: { type: Boolean, default: false },
})
const emit = defineEmits(['cancel', 'retry', 'resume', 'startOver'])

const logContainer = ref(null)

const stepStatuses = computed(() => {
  let foundActive = false
  return props.steps.map(step => {
    if (foundActive) return { label: step.label, status: 'pending' }
    if (step.stageNames.includes(props.currentStage)) {
      foundActive = true
      return { label: step.label, status: props.error ? 'error' : 'active' }
    }
    const laterSteps = props.steps.slice(props.steps.indexOf(step) + 1)
    const laterActive = laterSteps.some(s => s.stageNames.includes(props.currentStage))
    if (laterActive || props.currentStage === 'complete') {
      return { label: step.label, status: 'done' }
    }
    if (!props.currentStage) return { label: step.label, status: 'pending' }
    return { label: step.label, status: 'done' }
  })
})

const visibleLogs = computed(() => props.logEntries.slice(-50))
watch(() => props.logEntries.length, async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
})

const progressPercent = computed(() => {
  if (props.progress.total && props.progress.current) {
    return Math.round((props.progress.current / props.progress.total) * 100)
  }
  return null
})
</script>

<template>
  <div class="data-panel rounded-xl p-6 min-h-[400px] flex flex-col">
    <h2 class="text-xl font-bold mb-4" :style="{ fontFamily: 'var(--font-display)', color: 'var(--data-text)' }">{{ title }}</h2>

    <div class="mb-6">
      <StepIndicator :steps="stepStatuses" mode="pipeline" />
    </div>

    <div v-if="progressPercent !== null" class="mb-4">
      <div class="flex justify-between text-xs mb-1" :style="{ color: 'var(--data-text-muted)', fontFamily: 'var(--font-mono)' }">
        <span>{{ progress.current }} / {{ progress.total }}</span>
        <span>{{ progressPercent }}%</span>
      </div>
      <div class="h-1.5 rounded-full" :style="{ backgroundColor: 'var(--data-border)' }">
        <div
          class="h-full rounded-full transition-[width]"
          :style="{ width: progressPercent + '%', backgroundColor: 'var(--accent)', transitionDuration: '300ms', transitionTimingFunction: 'ease-out' }"
        />
      </div>
    </div>

    <div
      ref="logContainer"
      class="flex-1 rounded-lg p-4 overflow-y-auto font-mono text-xs space-y-1"
      :style="{ backgroundColor: 'var(--data-bg-raised)', border: '1px solid var(--data-border)', maxHeight: '240px' }"
    >
      <div
        v-for="(entry, i) in visibleLogs"
        :key="i"
        :style="{
          color: entry.type === 'success' ? 'var(--success)' : entry.type === 'error' ? 'var(--danger)' : 'var(--data-text-muted)',
          fontFamily: 'var(--font-mono)',
        }"
      >{{ entry.message }}</div>
    </div>

    <div v-if="disconnected && !error" class="mt-4 p-3 rounded-lg border flex items-center gap-2" :style="{ borderColor: 'var(--warning)', backgroundColor: 'rgba(245,158,11,0.1)' }">
      <span class="text-sm" :style="{ color: 'var(--warning)' }">Connection lost<span class="animate-pulse">...</span> reconnecting</span>
    </div>

    <div v-if="error" class="mt-4 p-3 rounded-lg border" :style="{
      borderColor: errorType === 'rate_limited' ? 'var(--warning)' : errorType === 'credits_exhausted' ? '#f97316' : 'var(--danger)',
      backgroundColor: errorType === 'rate_limited' ? 'rgba(245,158,11,0.1)' : errorType === 'credits_exhausted' ? 'rgba(249,115,22,0.1)' : 'rgba(239,68,68,0.1)',
    }">
      <p class="text-sm" :style="{
        color: errorType === 'rate_limited' ? 'var(--warning)' : errorType === 'credits_exhausted' ? '#f97316' : 'var(--danger)',
      }">{{ error }}</p>
    </div>

    <div class="mt-4 flex justify-end gap-3">
      <button
        v-if="error && resumable"
        class="px-4 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--accent)' }"
        @click="emit('resume')"
      >Resume</button>
      <button
        v-if="error && resumable"
        class="px-4 py-2 rounded-lg text-sm border"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
        @click="emit('startOver')"
      >Start Over</button>
      <button
        v-if="error && !resumable"
        class="px-4 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--accent)' }"
        @click="emit('retry')"
      >Retry</button>
      <button
        v-if="!error"
        class="px-4 py-2 rounded-lg text-sm border"
        :style="{ borderColor: 'var(--data-border)', color: 'var(--data-text-muted)' }"
        @click="emit('cancel')"
      >Cancel</button>
    </div>
  </div>
</template>
