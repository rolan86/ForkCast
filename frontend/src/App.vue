<script setup>
import { provide, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const toastRef = ref(null)

function toast(message, type = 'info', duration) {
  toastRef.value?.addToast(message, type, duration)
}

provide('toast', toast)
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
  <ToastContainer ref="toastRef" />
</template>
