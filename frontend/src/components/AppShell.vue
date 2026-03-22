<script setup>
import IconRail from './IconRail.vue'
</script>

<template>
  <div class="flex h-screen overflow-hidden" :style="{ backgroundColor: 'var(--surface)' }">
    <IconRail />
    <main class="flex-1 overflow-auto">
      <slot />
    </main>
  </div>
</template>
