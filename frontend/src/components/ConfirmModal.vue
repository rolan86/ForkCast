<script setup>
defineProps({
  title: { type: String, required: true },
  message: { type: String, required: true },
  confirmLabel: { type: String, default: 'Confirm' },
  variant: { type: String, default: 'danger', validator: v => ['danger', 'warning'].includes(v) },
})
const emit = defineEmits(['confirm', 'cancel'])

const variantColors = { danger: 'var(--danger)', warning: 'var(--warning)' }
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/50" @click="emit('cancel')" />
      <div
        class="relative rounded-xl border p-6 max-w-md w-full mx-4 animate-modal-in"
        :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-lg)' }"
      >
        <h3 class="text-lg font-semibold mb-2" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }">{{ title }}</h3>
        <p class="text-sm mb-6" :style="{ color: 'var(--text-secondary)', lineHeight: 1.5 }">{{ message }}</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 rounded-lg text-sm border"
            :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
            @click="emit('cancel')"
          >Cancel</button>
          <button
            class="px-4 py-2 rounded-lg text-sm font-medium text-white"
            :style="{ backgroundColor: variantColors[variant] }"
            @click="emit('confirm')"
          >{{ confirmLabel }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
@keyframes modal-in {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.animate-modal-in {
  animation: modal-in var(--duration-normal) var(--ease-out);
}
</style>
