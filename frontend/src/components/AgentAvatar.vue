<script setup>
import { computed } from 'vue'
import { avatarFromName } from '@/lib/avatar.js'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: String, default: 'md', validator: v => ['sm', 'md', 'lg'].includes(v) },
})

const sizes = { sm: '24px', md: '32px', lg: '40px' }
const fontSizes = { sm: '10px', md: '13px', lg: '16px' }

const avatar = computed(() => avatarFromName(props.name))
</script>

<template>
  <div
    class="rounded-full flex items-center justify-center text-white font-semibold shrink-0"
    :style="{
      width: sizes[size],
      height: sizes[size],
      fontSize: fontSizes[size],
      background: avatar.gradient,
      fontFamily: 'var(--font-body)',
    }"
  >{{ avatar.initials }}</div>
</template>
