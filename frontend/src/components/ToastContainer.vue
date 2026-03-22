<script setup>
import { ref } from 'vue'
import Toast from './Toast.vue'

const toasts = ref([])
let nextId = 0

function addToast(message, type = 'info', duration) {
  const id = nextId++
  const defaultDuration = type === 'success' ? 3000 : 5000
  toasts.value.push({ id, message, type, duration: duration || defaultDuration })
}

function dismiss(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

defineExpose({ addToast })
</script>

<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-2">
    <Toast
      v-for="toast in toasts"
      :key="toast.id"
      v-bind="toast"
      @dismiss="dismiss"
    />
  </div>
</template>
