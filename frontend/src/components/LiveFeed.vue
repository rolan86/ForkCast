<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import AgentAvatar from './AgentAvatar.vue'

const props = defineProps({
  actions: { type: Array, default: () => [] },
  platform: { type: String, default: 'twitter' },
})

const feedContainer = ref(null)
const autoScroll = ref(true)
const showNewPill = ref(false)

const actionTypeColors = {
  CREATE_POST: 'var(--accent)',
  tweet: 'var(--accent)',
  CREATE_COMMENT: 'var(--warning)',
  reply: 'var(--warning)',
  LIKE_POST: '#ec4899',
  like: '#ec4899',
  FOLLOW_USER: 'var(--success)',
  follow: 'var(--success)',
  DO_NOTHING: 'var(--text-tertiary)',
  do_nothing: 'var(--text-tertiary)',
}

const visibleActions = computed(() => props.actions.slice(0, 200))

function onScroll() {
  if (!feedContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = feedContainer.value
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50
  if (!isAtBottom) {
    autoScroll.value = false
    showNewPill.value = true
  } else {
    autoScroll.value = true
    showNewPill.value = false
  }
}

function scrollToLatest() {
  autoScroll.value = true
  showNewPill.value = false
  if (feedContainer.value) {
    feedContainer.value.scrollTop = 0
  }
}

watch(() => props.actions.length, async () => {
  if (autoScroll.value) {
    await nextTick()
    if (feedContainer.value) {
      feedContainer.value.scrollTop = 0
    }
  } else {
    showNewPill.value = true
  }
})
</script>

<template>
  <div class="data-panel rounded-xl overflow-hidden flex flex-col" style="max-height: 500px;">
    <div class="px-4 py-3 border-b flex items-center justify-between" :style="{ borderColor: 'var(--data-border)' }">
      <span
        class="text-xs uppercase tracking-wider font-medium"
        :style="{ color: 'var(--data-text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }"
      >Live Feed — {{ platform }}</span>
      <span class="text-xs" :style="{ color: 'var(--data-text-muted)', fontFamily: 'var(--font-mono)' }">{{ actions.length }} actions</span>
    </div>

    <div ref="feedContainer" class="flex-1 overflow-y-auto relative" @scroll="onScroll">
      <div
        v-for="(action, i) in visibleActions"
        :key="action.id || i"
        class="px-4 py-3 border-b flex gap-3 animate-action-in"
        :style="{ borderColor: 'var(--data-border)', animationDelay: i < 1 ? '0ms' : 'none' }"
      >
        <AgentAvatar :name="action.agent_name || 'Unknown'" size="sm" />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-sm font-semibold truncate" :style="{ color: 'var(--data-text)', fontFamily: 'var(--font-mono)' }">
              {{ action.agent_name }}
            </span>
            <span
              class="text-xs px-1.5 py-0.5 rounded"
              :style="{ backgroundColor: (actionTypeColors[action.action_type] || 'var(--accent)') + '22', color: actionTypeColors[action.action_type] || 'var(--accent)' }"
            >{{ action.action_type }}</span>
          </div>
          <p
            v-if="action.action_args?.content"
            class="text-sm line-clamp-2"
            :style="{ color: 'var(--data-text-muted)' }"
          >{{ action.action_args.content }}</p>
        </div>
      </div>

      <div v-if="!actions.length" class="py-12 text-center">
        <p class="text-sm" :style="{ color: 'var(--data-text-muted)' }">Waiting for actions...</p>
      </div>
    </div>

    <button
      v-if="showNewPill"
      class="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full text-xs font-medium text-white z-10"
      :style="{ backgroundColor: 'var(--accent)' }"
      @click="scrollToLatest"
    >↓ New actions</button>
  </div>
</template>

<style scoped>
@keyframes action-in {
  from { transform: translateY(-8px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
@keyframes highlight-fade {
  from { border-left-color: var(--accent); }
  to { border-left-color: transparent; }
}
.animate-action-in:first-child {
  animation: action-in 50ms var(--ease-out), highlight-fade 800ms ease-out;
  border-left: 2px solid var(--accent);
}
</style>
