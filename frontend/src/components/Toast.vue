<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps({
  id: { type: [String, Number], required: true },
  message: { type: String, required: true },
  type: { type: String, default: 'info', validator: v => ['error', 'success', 'info'].includes(v) },
  duration: { type: Number, default: 5000 },
})
const emit = defineEmits(['dismiss'])

const borderColors = { error: 'var(--danger)', success: 'var(--success)', info: 'var(--accent)' }
const progress = ref(100)
let startTime = 0
let rafId = null

function tick() {
  const elapsed = Date.now() - startTime
  progress.value = Math.max(0, 100 - (elapsed / props.duration) * 100)
  if (progress.value <= 0) {
    emit('dismiss', props.id)
    return
  }
  rafId = requestAnimationFrame(tick)
}

onMounted(() => {
  startTime = Date.now()
  rafId = requestAnimationFrame(tick)
})

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
})
</script>

<template>
  <div
    class="relative rounded-lg border overflow-hidden shadow-lg animate-slide-in"
    :style="{
      backgroundColor: 'var(--surface-raised)',
      borderColor: 'var(--border)',
      borderLeftWidth: '3px',
      borderLeftColor: borderColors[type],
      minWidth: '320px',
      maxWidth: '420px',
    }"
  >
    <div class="flex items-start gap-3 p-4">
      <p class="flex-1 text-sm" :style="{ color: 'var(--text-primary)' }">{{ message }}</p>
      <button @click="emit('dismiss', id)" class="shrink-0 opacity-50 hover:opacity-100">
        <X :size="14" :style="{ color: 'var(--text-secondary)' }" />
      </button>
    </div>
    <div
      class="h-0.5 absolute bottom-0 left-0 transition-none"
      :style="{ width: progress + '%', backgroundColor: borderColors[type], opacity: 0.5 }"
    />
  </div>
</template>

<style scoped>
@keyframes slide-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.animate-slide-in {
  animation: slide-in var(--duration-slow) var(--ease-spring);
}
</style>
