<script setup>
import * as icons from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  subtitle: { type: String, default: '' },
  icon: { type: String, default: '' },
  trend: { type: String, default: '', validator: v => ['', 'up', 'down', 'neutral'].includes(v) },
})

const IconComponent = computed(() => props.icon ? icons[props.icon] : null)
</script>

<template>
  <div
    class="rounded-lg border p-5 transition-all cursor-default"
    :style="{
      backgroundColor: 'var(--surface-raised)',
      borderColor: 'var(--border)',
      boxShadow: 'var(--shadow-sm)',
    }"
    @mouseenter="$el.style.transform = 'translateY(-1px)'; $el.style.boxShadow = 'var(--shadow-md)'"
    @mouseleave="$el.style.transform = ''; $el.style.boxShadow = 'var(--shadow-sm)'"
  >
    <div class="flex items-center gap-2 mb-2">
      <component v-if="IconComponent" :is="IconComponent" :size="14" :style="{ color: 'var(--text-tertiary)' }" />
      <span
        class="text-xs uppercase tracking-wider"
        :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }"
      >{{ label }}</span>
    </div>
    <div class="text-3xl font-bold" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }">{{ value }}</div>
    <div v-if="subtitle" class="mt-1 text-sm" :style="{ color: 'var(--text-secondary)' }">{{ subtitle }}</div>
  </div>
</template>
