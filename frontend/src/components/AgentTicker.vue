<script setup>
import { ref } from 'vue'

const props = defineProps({
  fallbackText: { type: String, default: '' },
})

const queue = ref([])
const current = ref(null)
const transitioning = ref(false)
let timer = null

function push(entry) {
  queue.value.push(entry)
  if (!current.value && !transitioning.value) {
    showNext()
  }
}

function showNext() {
  if (queue.value.length === 0) {
    current.value = null
    return
  }
  transitioning.value = true
  current.value = queue.value.shift()
  transitioning.value = false

  timer = setTimeout(() => {
    if (queue.value.length > 0) {
      transitioning.value = true
      setTimeout(() => showNext(), 200)
    }
  }, 2000)
}

defineExpose({ push })
</script>

<template>
  <div class="agent-ticker">
    <Transition name="ticker-slide" mode="out-in">
      <div v-if="current" :key="current.name" class="agent-ticker__entry">
        <span class="agent-ticker__name">{{ current.name }}</span>
        <span class="agent-ticker__sep">&mdash;</span>
        <span class="agent-ticker__bio">"{{ current.bio }}"</span>
      </div>
      <div v-else-if="fallbackText" class="agent-ticker__fallback">
        {{ fallbackText }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.agent-ticker {
  height: 48px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  background: rgba(9, 9, 11, 0.85);
  border-top: 1px solid var(--data-border);
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 12px;
}
.agent-ticker__entry {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent-ticker__name {
  color: var(--accent);
  font-weight: 600;
}
.agent-ticker__sep {
  color: var(--data-text-muted);
  margin: 0 8px;
}
.agent-ticker__bio {
  color: var(--data-text-muted);
  font-style: italic;
}
.agent-ticker__fallback {
  color: var(--data-text-muted);
}

.ticker-slide-enter-active,
.ticker-slide-leave-active {
  transition: all 250ms var(--ease-out);
}
.ticker-slide-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.ticker-slide-leave-to {
  opacity: 0;
  transform: translateX(-40px);
}
</style>
