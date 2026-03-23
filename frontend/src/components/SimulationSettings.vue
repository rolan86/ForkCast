<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useCapabilitiesStore } from '@/stores/capabilities.js'
import { updateSettings } from '@/api/simulations.js'
import PlatformBadge from './PlatformBadge.vue'

const props = defineProps({
  simulation: { type: Object, required: true },
  reusableProfiles: { type: Object, default: null },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['updated'])

const caps = useCapabilitiesStore()
onMounted(() => caps.fetch())

const engine = ref(props.simulation.engine_type || 'claude')
const platforms = ref(props.simulation.platforms || ['twitter', 'reddit'])
const prepModel = ref(props.simulation.prep_model || 'claude-haiku-4-5')
const runModel = ref(props.simulation.run_model || 'claude-sonnet-4-6')
const forceRegenerate = ref(false)
const agentMode = ref(props.simulation.agent_mode || 'llm')
const saving = ref(false)

defineExpose({ forceRegenerate })

watch(() => props.simulation, (sim) => {
  engine.value = sim.engine_type || 'claude'
  platforms.value = sim.platforms || ['twitter', 'reddit']
  prepModel.value = sim.prep_model || 'claude-haiku-4-5'
  runModel.value = sim.run_model || 'claude-sonnet-4-6'
  agentMode.value = sim.agent_mode || 'llm'
}, { deep: true })

const oasisDisabled = computed(() => !caps.isOasisAvailable)
const showAgentMode = computed(() => engine.value === 'oasis' && !oasisDisabled.value)

function togglePlatform(p) {
  if (props.readonly) return
  const idx = platforms.value.indexOf(p)
  if (idx >= 0 && platforms.value.length > 1) {
    platforms.value.splice(idx, 1)
  } else if (idx < 0) {
    platforms.value.push(p)
  }
}

async function save() {
  if (props.readonly) return
  saving.value = true
  try {
    await updateSettings(props.simulation.id, {
      engine_type: engine.value,
      platforms: platforms.value,
      prep_model: prepModel.value,
      run_model: runModel.value,
      agent_mode: agentMode.value,
    })
    emit('updated')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h4 class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">
        Settings
      </h4>
      <button
        v-if="!readonly"
        class="text-xs px-3 py-1 rounded-md"
        :style="{ backgroundColor: 'var(--accent)', color: 'white' }"
        :disabled="saving"
        @click="save"
      >{{ saving ? 'Saving...' : 'Save' }}</button>
    </div>

    <!-- Engine -->
    <div>
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Engine</label>
      <div class="flex gap-2">
        <button
          v-for="e in ['claude', 'oasis']"
          :key="e"
          class="px-3 py-1.5 rounded-md text-sm border transition-colors"
          :style="{
            backgroundColor: engine === e ? 'var(--accent-surface)' : 'transparent',
            borderColor: engine === e ? 'var(--accent)' : 'var(--border)',
            color: engine === e ? 'var(--accent)' : 'var(--text-secondary)',
            opacity: (e === 'oasis' && oasisDisabled) || readonly ? 0.4 : 1,
            cursor: (e === 'oasis' && oasisDisabled) || readonly ? 'not-allowed' : 'pointer',
          }"
          :disabled="(e === 'oasis' && oasisDisabled) || readonly"
          :title="e === 'oasis' && oasisDisabled ? 'Not available — install with: uv add camel-oasis' : ''"
          @click="engine = e"
        >{{ e === 'claude' ? 'Claude API' : 'OASIS' }}</button>
      </div>
    </div>

    <!-- Agent Mode (OASIS only) -->
    <div v-if="showAgentMode">
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Agent Mode</label>
      <div class="flex gap-2">
        <button
          v-for="mode in [
            { value: 'llm', label: 'LLM-driven', sub: 'AI decides actions · costs tokens' },
            { value: 'native', label: 'Rule-based', sub: 'Activity patterns · fast, free' },
          ]"
          :key="mode.value"
          class="flex-1 px-3 py-2 rounded-md text-sm border transition-colors text-left"
          :style="{
            backgroundColor: agentMode === mode.value ? 'var(--accent-surface)' : 'transparent',
            borderColor: agentMode === mode.value ? 'var(--accent)' : 'var(--border)',
            color: agentMode === mode.value ? 'var(--accent)' : 'var(--text-secondary)',
            opacity: readonly ? 0.4 : 1,
            cursor: readonly ? 'not-allowed' : 'pointer',
          }"
          :disabled="readonly"
          @click="agentMode = mode.value"
        >
          <span class="block font-medium">{{ mode.label }}</span>
          <span class="block text-xs mt-0.5 opacity-70">{{ mode.sub }}</span>
        </button>
      </div>
    </div>

    <!-- Platforms -->
    <div>
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Platforms</label>
      <div class="flex gap-2">
        <button
          v-for="p in ['twitter', 'reddit']"
          :key="p"
          class="px-3 py-1.5 rounded-md text-sm border transition-colors flex items-center gap-1.5"
          :style="{
            backgroundColor: platforms.includes(p) ? 'var(--accent-surface)' : 'transparent',
            borderColor: platforms.includes(p) ? 'var(--accent)' : 'var(--border)',
            color: platforms.includes(p) ? 'var(--accent)' : 'var(--text-secondary)',
            opacity: readonly ? 0.6 : 1,
          }"
          :disabled="readonly"
          @click="togglePlatform(p)"
        >
          <PlatformBadge :platform="p" size="sm" />
          {{ p }}
        </button>
      </div>
    </div>

    <!-- Models -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Prep Model</label>
        <select
          v-model="prepModel"
          :disabled="readonly"
          class="w-full px-2 py-1.5 rounded-md text-sm border"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)', color: 'var(--text-primary)' }"
        >
          <option v-for="m in caps.models" :key="m.id" :value="m.id">{{ m.label }}</option>
        </select>
      </div>
      <div>
        <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Run Model</label>
        <select
          v-model="runModel"
          :disabled="readonly"
          class="w-full px-2 py-1.5 rounded-md text-sm border"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)', color: 'var(--text-primary)' }"
        >
          <option v-for="m in caps.models" :key="m.id" :value="m.id">{{ m.label }}</option>
        </select>
      </div>
    </div>

    <!-- Profile Reuse -->
    <div v-if="reusableProfiles && !readonly">
      <div class="p-3 rounded-lg border" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-sunken)' }">
        <p class="text-xs" :style="{ color: 'var(--text-secondary)' }">
          {{ reusableProfiles.count }} profiles available from previous simulation
        </p>
        <label class="flex items-center gap-2 mt-2 cursor-pointer">
          <input type="checkbox" v-model="forceRegenerate" />
          <span class="text-xs" :style="{ color: 'var(--text-secondary)' }">Regenerate profiles</span>
        </label>
      </div>
    </div>
  </div>
</template>
