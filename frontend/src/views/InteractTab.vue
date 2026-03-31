<script setup>
import { ref } from 'vue'

const activeMode = ref('interview')
</script>

<template>
  <div :style="{ display: 'flex', height: '100%', fontFamily: 'var(--font-body)' }">
    <div :style="{
      width: '260px',
      backgroundColor: 'var(--interact-sidebar-bg)',
      color: 'var(--interact-sidebar-text)',
      padding: '16px',
      fontFamily: 'var(--font-mono)',
      fontSize: '12px',
    }">
      Interact sidebar placeholder
    </div>
    <div :style="{ flex: 1, padding: '24px' }">
      <p>Interact tab — {{ activeMode }} mode</p>
    </div>
  </div>
</template>
