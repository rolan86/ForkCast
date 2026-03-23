<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: { type: Object, default: null },
  simulation: { type: Object, default: null },
})

const timing = computed(() => {
  if (!props.config) return null
  const rounds = Math.ceil((props.config.total_hours * 60) / (props.config.minutes_per_round || 30))
  return `${rounds} rounds, ${props.config.minutes_per_round}min/round (${props.config.total_hours}h simulated)`
})
</script>

<template>
  <div v-if="config || simulation" class="space-y-3">
    <h4 class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">
      Configuration
    </h4>
    <div v-if="simulation" class="grid grid-cols-2 gap-3 text-sm">
      <div>
        <span class="text-xs block" :style="{ color: 'var(--text-tertiary)' }">Engine</span>
        <span :style="{ color: 'var(--text-primary)' }">{{ simulation.engine_type === 'claude' ? 'Claude API' : 'OASIS' }}</span>
      </div>
      <div>
        <span class="text-xs block" :style="{ color: 'var(--text-tertiary)' }">Prep / Run Model</span>
        <span :style="{ color: 'var(--text-primary)' }">{{ simulation.prep_model || 'Haiku 4.5' }} / {{ simulation.run_model || 'Sonnet 4.6' }}</span>
      </div>
      <div v-if="simulation.profile_source">
        <span class="text-xs block" :style="{ color: 'var(--text-tertiary)' }">Profile Source</span>
        <span :style="{ color: 'var(--text-primary)' }">{{ simulation.profile_source }}</span>
      </div>
    </div>

    <template v-if="config">
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span class="text-xs block" :style="{ color: 'var(--text-tertiary)' }">Timing</span>
          <span :style="{ color: 'var(--text-primary)' }">{{ timing }}</span>
        </div>
        <div v-if="config.narrative_direction">
          <span class="text-xs block" :style="{ color: 'var(--text-tertiary)' }">Direction</span>
          <span :style="{ color: 'var(--text-primary)' }">{{ config.narrative_direction }}</span>
        </div>
      </div>
      <div v-if="config.hot_topics?.length" class="flex flex-wrap gap-1">
        <span
          v-for="topic in config.hot_topics"
          :key="topic"
          class="px-2 py-0.5 rounded text-xs"
          :style="{ backgroundColor: 'var(--accent-surface)', color: 'var(--accent)' }"
        >{{ topic }}</span>
      </div>
      <div v-if="config.seed_posts?.length">
        <span class="text-xs block mb-1" :style="{ color: 'var(--text-tertiary)' }">Seed Posts</span>
        <div class="space-y-1">
          <p v-for="(post, i) in config.seed_posts.slice(0, 3)" :key="i" class="text-xs truncate" :style="{ color: 'var(--text-secondary)' }">
            {{ post }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>
