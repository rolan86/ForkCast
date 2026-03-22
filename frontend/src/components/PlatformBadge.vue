<script setup>
defineProps({
  platform: { type: String, required: true, validator: v => ['twitter', 'reddit'].includes(v) },
  size: { type: String, default: 'sm', validator: v => ['sm', 'md'].includes(v) },
})

const platformConfig = {
  twitter: { label: 'Twitter', emoji: '𝕏', bg: '#18181b', color: '#ffffff' },
  reddit: { label: 'Reddit', emoji: '🤖', bg: '#ff4500', color: '#ffffff' },
}
</script>

<template>
  <span
    v-if="size === 'sm'"
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
    :style="{ backgroundColor: platformConfig[platform].bg, color: platformConfig[platform].color }"
  >
    {{ platformConfig[platform].emoji }} {{ platformConfig[platform].label }}
  </span>
  <div
    v-else
    class="inline-flex items-center gap-2 px-4 py-3 rounded-lg border"
    :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }"
  >
    <span class="text-xl">{{ platformConfig[platform].emoji }}</span>
    <span class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">{{ platformConfig[platform].label }}</span>
  </div>
</template>
