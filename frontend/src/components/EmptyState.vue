<script setup>
import * as icons from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  actionLabel: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  disabledTooltip: { type: String, default: '' },
})
const emit = defineEmits(['action'])

const IconComponent = computed(() => icons[props.icon] || icons.HelpCircle)
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 px-8 text-center">
    <component :is="IconComponent" :size="48" :style="{ color: 'var(--text-tertiary)', opacity: 0.3 }" />
    <h3 class="mt-4 text-lg font-semibold" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }">{{ title }}</h3>
    <p class="mt-2 text-sm max-w-xs" :style="{ color: 'var(--text-secondary)', lineHeight: 1.5 }">{{ description }}</p>
    <button
      v-if="actionLabel"
      class="mt-6 px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all"
      :style="{
        backgroundColor: disabled ? 'var(--text-tertiary)' : 'var(--accent)',
        cursor: disabled ? 'not-allowed' : 'pointer',
      }"
      :disabled="disabled"
      :title="disabled ? disabledTooltip : ''"
      @click="!disabled && emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
