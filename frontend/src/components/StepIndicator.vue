<script setup>
defineProps({
  steps: { type: Array, required: true },
  mode: { type: String, default: 'pipeline', validator: v => ['wizard', 'pipeline'].includes(v) },
})
</script>

<template>
  <!-- Wizard mode: numbered circles connected by lines -->
  <div v-if="mode === 'wizard'" class="flex items-center gap-2">
    <template v-for="(step, i) in steps" :key="i">
      <div class="flex items-center gap-2">
        <div
          class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 transition-colors"
          :style="{
            backgroundColor: step.status === 'done' ? 'var(--accent)' : step.status === 'active' ? 'var(--accent)' : 'transparent',
            color: step.status !== 'pending' ? 'white' : 'var(--text-tertiary)',
            border: step.status === 'pending' ? '2px solid var(--border)' : 'none',
            fontFamily: 'var(--font-mono)',
          }"
        >{{ i + 1 }}</div>
        <span
          class="text-sm whitespace-nowrap"
          :style="{ color: step.status === 'active' ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: step.status === 'active' ? 600 : 400 }"
        >{{ step.label }}</span>
      </div>
      <div
        v-if="i < steps.length - 1"
        class="flex-1 h-px min-w-[24px]"
        :style="{ backgroundColor: steps[i + 1]?.status !== 'pending' ? 'var(--accent)' : 'var(--border)' }"
      />
    </template>
  </div>

  <!-- Pipeline mode: segmented bars -->
  <div v-else class="flex gap-1">
    <div
      v-for="(step, i) in steps"
      :key="i"
      class="flex-1 flex flex-col gap-1"
    >
      <div
        class="h-1.5 rounded-full transition-colors"
        :style="{
          backgroundColor: step.status === 'done' ? 'var(--success)' : step.status === 'active' ? 'var(--warning)' : 'var(--border)',
          transitionDuration: 'var(--duration-normal)',
        }"
      />
      <span
        class="text-xs truncate"
        :style="{
          color: step.status === 'active' ? 'var(--text-primary)' : 'var(--text-secondary)',
          fontWeight: step.status === 'active' ? 500 : 400,
        }"
      >{{ step.label }}</span>
    </div>
  </div>
</template>
