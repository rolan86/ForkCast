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

// Token optimization settings (Claude engine only)
const simConfig = props.simulation.config || {}
const decisionModel = ref(simConfig.decision_model || 'claude-haiku-4-5')
const creativeModel = ref(simConfig.creative_model || 'claude-sonnet-4-6')
const compressFeed = ref(simConfig.compress_feed || false)

const TIMING_PRESETS = [
  { label: 'Quick Test', hours: 6, interval: 30 },
  { label: 'Standard', hours: 48, interval: 30 },
  { label: 'Extended', hours: 168, interval: 30 },
]

const totalHours = ref(props.simulation.total_hours || 48)
const minutesPerRound = ref(props.simulation.minutes_per_round || 30)
const activePreset = ref('Standard')

const computedRounds = computed(() => Math.ceil(totalHours.value * 60 / minutesPerRound.value))

function selectPreset(preset) {
  if (props.readonly) return
  totalHours.value = preset.hours
  minutesPerRound.value = preset.interval
  activePreset.value = preset.label
}

function onSliderChange() {
  const match = TIMING_PRESETS.find(p => p.hours === totalHours.value && p.interval === minutesPerRound.value)
  activePreset.value = match ? match.label : 'Custom'
}

const estimateText = computed(() => {
  const rounds = computedRounds.value
  const agentCount = props.reusableProfiles?.count || 15
  let seconds
  if (engine.value === 'oasis' && agentMode.value === 'native') {
    seconds = rounds * 0.5
  } else if (engine.value === 'oasis') {
    seconds = rounds * agentCount * 2
  } else {
    seconds = rounds * agentCount * 3
  }
  const lo = seconds * 0.7
  const hi = seconds * 1.3
  const fmt = (s) => {
    if (s < 60) return '< 1 min'
    if (s < 3600) return `${Math.round(s / 60)} min`
    return `${(s / 3600).toFixed(1)} hours`
  }
  if (hi < 60) return '< 1 min'
  return `≈ ${fmt(lo)}–${fmt(hi)}`
})

defineExpose({ forceRegenerate, totalHours, minutesPerRound })

watch(() => props.simulation, (sim) => {
  engine.value = sim.engine_type || 'claude'
  platforms.value = sim.platforms || ['twitter', 'reddit']
  prepModel.value = sim.prep_model || 'claude-haiku-4-5'
  runModel.value = sim.run_model || 'claude-sonnet-4-6'
  agentMode.value = sim.agent_mode || 'llm'
  totalHours.value = sim.total_hours || 48
  minutesPerRound.value = sim.minutes_per_round || 30
  const cfg = sim.config || {}
  decisionModel.value = cfg.decision_model || 'claude-haiku-4-5'
  creativeModel.value = cfg.creative_model || 'claude-sonnet-4-6'
  compressFeed.value = cfg.compress_feed || false
  const match = TIMING_PRESETS.find(p => p.hours === totalHours.value && p.interval === minutesPerRound.value)
  activePreset.value = match ? match.label : 'Custom'
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
    const payload = {
      engine_type: engine.value,
      platforms: platforms.value,
      prep_model: prepModel.value,
      run_model: runModel.value,
      agent_mode: agentMode.value,
      total_hours: totalHours.value,
      minutes_per_round: minutesPerRound.value,
    }
    // Include optimization fields only for Claude engine
    if (engine.value === 'claude') {
      payload.decision_model = decisionModel.value
      payload.creative_model = creativeModel.value
      payload.compress_feed = compressFeed.value
    }
    await updateSettings(props.simulation.id, payload)
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

    <!-- Timing -->
    <div>
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">
        Simulation Duration
      </label>
      <p class="text-xs mb-3" :style="{ color: 'var(--text-tertiary)' }">
        How long to simulate and how detailed each step should be
      </p>

      <!-- Presets -->
      <div v-if="!readonly" class="flex gap-2 mb-4">
        <button
          v-for="preset in TIMING_PRESETS"
          :key="preset.label"
          class="px-3 py-1.5 rounded-md text-sm border transition-colors"
          :style="{
            backgroundColor: activePreset === preset.label ? 'var(--accent-surface)' : 'transparent',
            borderColor: activePreset === preset.label ? 'var(--accent)' : 'var(--border)',
            color: activePreset === preset.label ? 'var(--accent)' : 'var(--text-secondary)',
          }"
          @click="selectPreset(preset)"
        >{{ preset.label }}</button>
        <button
          class="px-3 py-1.5 rounded-md text-sm border transition-colors"
          :style="{
            backgroundColor: activePreset === 'Custom' ? 'var(--accent-surface)' : 'transparent',
            borderColor: activePreset === 'Custom' ? 'var(--accent)' : 'var(--border)',
            color: activePreset === 'Custom' ? 'var(--accent)' : 'var(--text-secondary)',
          }"
        >Custom</button>
      </div>

      <!-- Sliders (editable) or static display (readonly) -->
      <template v-if="!readonly">
        <div class="space-y-3">
          <div>
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs" :style="{ color: 'var(--text-secondary)' }">Simulated Hours</span>
              <span class="text-xs font-mono" :style="{ color: 'var(--text-primary)' }">{{ totalHours }}h</span>
            </div>
            <input
              type="range"
              :min="1" :max="168" :step="1"
              v-model.number="totalHours"
              @input="onSliderChange"
              class="w-full accent-[var(--accent)]"
            />
            <p class="text-xs mt-0.5" :style="{ color: 'var(--text-tertiary)' }">The fictional timespan being modeled</p>
          </div>
          <div>
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs" :style="{ color: 'var(--text-secondary)' }">Round Interval</span>
              <span class="text-xs font-mono" :style="{ color: 'var(--text-primary)' }">{{ minutesPerRound }} min</span>
            </div>
            <input
              type="range"
              :min="10" :max="60" :step="5"
              v-model.number="minutesPerRound"
              @input="onSliderChange"
              class="w-full accent-[var(--accent)]"
            />
            <p class="text-xs mt-0.5" :style="{ color: 'var(--text-tertiary)' }">How much simulated time passes per step — shorter = more detail, more steps</p>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="text-sm" :style="{ color: 'var(--text-primary)' }">
          {{ totalHours }}h simulated · {{ minutesPerRound }} min/round
        </div>
      </template>

      <!-- Summary box -->
      <div class="mt-3 p-3 rounded-lg" :style="{ backgroundColor: 'var(--surface-sunken)' }">
        <p class="text-sm font-medium" :style="{ color: 'var(--text-primary)' }">
          {{ computedRounds }} rounds · {{ totalHours }} simulated hours
        </p>
        <p class="text-xs mt-0.5" :style="{ color: 'var(--text-tertiary)' }">
          {{ estimateText }} with {{ engine === 'oasis' && agentMode === 'native' ? 'OASIS native' : engine === 'oasis' ? 'OASIS LLM' : 'Claude' }} engine
        </p>
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

    <!-- Token Optimization (Claude engine only) -->
    <div v-if="engine === 'claude'">
      <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Token Optimization</label>
      <p class="text-xs mb-3" :style="{ color: 'var(--text-tertiary)' }">
        Reduce API costs with two-phase model routing and feed compression
      </p>
      <div class="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Decision Model</label>
          <select
            v-model="decisionModel"
            :disabled="readonly"
            class="w-full px-2 py-1.5 rounded-md text-sm border"
            :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)', color: 'var(--text-primary)' }"
          >
            <option v-for="m in caps.models" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <p class="text-xs mt-0.5" :style="{ color: 'var(--text-tertiary)' }">Cheap model for action decisions</p>
        </div>
        <div>
          <label class="text-xs mb-1 block" :style="{ color: 'var(--text-secondary)' }">Creative Model</label>
          <select
            v-model="creativeModel"
            :disabled="readonly"
            class="w-full px-2 py-1.5 rounded-md text-sm border"
            :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)', color: 'var(--text-primary)' }"
          >
            <option v-for="m in caps.models" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <p class="text-xs mt-0.5" :style="{ color: 'var(--text-tertiary)' }">Full model for content creation</p>
        </div>
      </div>
      <label class="flex items-center gap-2" :class="{ 'cursor-pointer': !readonly, 'opacity-60': readonly }">
        <input type="checkbox" v-model="compressFeed" :disabled="readonly" />
        <span class="text-xs" :style="{ color: 'var(--text-secondary)' }">
          Compress feed context
          <span :style="{ color: 'var(--text-tertiary)' }">(reduces cost, may slightly reduce interaction specificity)</span>
        </span>
      </label>
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
