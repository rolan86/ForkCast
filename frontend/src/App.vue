<script setup>
import { onMounted, provide, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useCapabilitiesStore } from '@/stores/capabilities.js'

const capStore = useCapabilitiesStore()
const toastRef = ref(null)

function toast(message, type = 'info', duration) {
  toastRef.value?.addToast(message, type, duration)
}

provide('toast', toast)

onMounted(() => capStore.fetch())
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
  <ToastContainer ref="toastRef" />
</template>
