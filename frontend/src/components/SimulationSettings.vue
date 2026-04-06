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

// Dynamics settings
const circadianEnabled = ref(simConfig.circadian_enabled ?? true)
const engagementEnabled = ref(simConfig.engagement_enabled ?? true)
const integratorMethod = ref(simConfig.integrator_method ?? 'euler')
const integratorOrder = ref(simConfig.integrator_order ?? 4)
const integratorTolerance = ref(simConfig.integrator_tolerance ?? 1e-6)
const integratorMaxOrder = ref(simConfig.integrator_max_order ?? 8)
const dynamicsExpanded = ref(false)

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
  circadianEnabled.value = cfg.circadian_enabled ?? true
  engagementEnabled.value = cfg.engagement_enabled ?? true
  integratorMethod.value = cfg.integrator_method ?? 'euler'
  integratorOrder.value = cfg.integrator_order ?? 4
  integratorTolerance.value = cfg.integrator_tolerance ?? 1e-6
  integratorMaxOrder.value = cfg.integrator_max_order ?? 8
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
      payload.circadian_enabled = circadianEnabled.value
      payload.engagement_enabled = engagementEnabled.value
      payload.integrator_method = integratorMethod.value
      if (integratorMethod.value === 'rk') {
        payload.integrator_order = integratorOrder.value
      }
      if (integratorMethod.value === 'adaptive') {
        payload.integrator_tolerance = integratorTolerance.value
        payload.integrator_max_order = integratorMaxOrder.value
      }
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

    <!-- Advanced Dynamics (Claude engine only) -->
    <div v-if="engine === 'claude'" class="dynamics-section">
      <button
        class="dynamics-trigger"
        :class="{ 'dynamics-trigger--open': dynamicsExpanded }"
        :disabled="readonly"
        @click="dynamicsExpanded = !dynamicsExpanded"
      >
        <div class="dynamics-trigger__left">
          <span class="dynamics-trigger__icon">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L8 14M5 5C5 5 6.5 3.5 8 3.5C9.5 3.5 11 5 11 5M4 8.5C4 8.5 5.5 6.5 8 6.5C10.5 6.5 12 8.5 12 8.5M3 12C3 12 5 9.5 8 9.5C11 9.5 13 12 13 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </span>
          <div>
            <span class="dynamics-trigger__title">ODE Dynamics</span>
            <span class="dynamics-trigger__subtitle">Circadian rhythms · Engagement growth · Numerical integration</span>
          </div>
        </div>
        <span class="dynamics-trigger__chevron" :class="{ 'dynamics-trigger__chevron--open': dynamicsExpanded }">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M4.5 3L7.5 6L4.5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
      </button>

      <Transition name="dynamics-expand">
        <div v-show="dynamicsExpanded" class="dynamics-body">
          <div class="dynamics-body__inner">
            <!-- Circadian toggle -->
            <label class="dynamics-toggle" :class="{ 'dynamics-toggle--disabled': readonly }">
              <span class="dynamics-toggle__track" :class="{ 'dynamics-toggle__track--on': circadianEnabled }">
                <input type="checkbox" v-model="circadianEnabled" :disabled="readonly" class="sr-only" />
                <span class="dynamics-toggle__thumb" :class="{ 'dynamics-toggle__thumb--on': circadianEnabled }"></span>
              </span>
              <div>
                <span class="dynamics-toggle__label">Circadian Agent Rhythms</span>
                <span class="dynamics-toggle__desc">Agents have natural activity cycles — early birds, night owls</span>
              </div>
            </label>

            <!-- Engagement toggle -->
            <label class="dynamics-toggle" :class="{ 'dynamics-toggle--disabled': readonly }">
              <span class="dynamics-toggle__track" :class="{ 'dynamics-toggle__track--on': engagementEnabled }">
                <input type="checkbox" v-model="engagementEnabled" :disabled="readonly" class="sr-only" />
                <span class="dynamics-toggle__thumb" :class="{ 'dynamics-toggle__thumb--on': engagementEnabled }"></span>
              </span>
              <div>
                <span class="dynamics-toggle__label">Engagement Dynamics</span>
                <span class="dynamics-toggle__desc">Posts gain traction following logistic growth curves</span>
              </div>
            </label>

            <!-- Integration Method -->
            <div v-if="circadianEnabled || engagementEnabled" class="dynamics-integrators">
              <div class="dynamics-integrators__divider"></div>
              <label class="text-xs mb-2 block font-medium" :style="{ color: 'var(--text-secondary)', letterSpacing: '0.02em' }">Numerical Integrator</label>
              <div class="dynamics-integrators__grid">
                <button
                  v-for="method in caps.integrators"
                  :key="method.id"
                  class="dynamics-method"
                  :class="{
                    'dynamics-method--selected': integratorMethod === method.id,
                    'dynamics-method--disabled': readonly
                  }"
                  :disabled="readonly"
                  @click="integratorMethod = method.id"
                >
                  <span class="dynamics-method__dot"></span>
                  <div>
                    <span class="dynamics-method__name">{{ method.name }}</span>
                    <span class="dynamics-method__desc">{{ method.description }}</span>
                  </div>
                </button>
              </div>

              <!-- RK order selector -->
              <div v-if="integratorMethod === 'rk'" class="dynamics-param">
                <label class="dynamics-param__label">RK Order</label>
                <div class="dynamics-param__chips">
                  <button
                    v-for="o in [2, 4, 6, 8]" :key="o"
                    class="dynamics-chip"
                    :class="{ 'dynamics-chip--active': integratorOrder === o }"
                    :disabled="readonly"
                    @click="integratorOrder = o"
                  >{{ o }}</button>
                </div>
              </div>

              <!-- Adaptive params -->
              <template v-if="integratorMethod === 'adaptive'">
                <div class="dynamics-param">
                  <label class="dynamics-param__label">Tolerance</label>
                  <input
                    type="number"
                    v-model.number="integratorTolerance"
                    step="0.000001" min="0.000001"
                    :disabled="readonly"
                    class="dynamics-param__input"
                  />
                </div>
                <div class="dynamics-param">
                  <label class="dynamics-param__label">Max Order</label>
                  <div class="dynamics-param__chips">
                    <button
                      v-for="o in [2, 4, 6, 8]" :key="o"
                      class="dynamics-chip"
                      :class="{ 'dynamics-chip--active': integratorMaxOrder === o }"
                      :disabled="readonly"
                      @click="integratorMaxOrder = o"
                    >{{ o }}</button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </Transition>
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

<style scoped>
/* === Dynamics Section === */
.dynamics-section {
  border-radius: 10px;
  border: 1px solid var(--border);
  background: linear-gradient(135deg, var(--surface-raised) 0%, var(--surface-sunken) 100%);
  overflow: hidden;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.dynamics-section:has(.dynamics-trigger--open) {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 8%, transparent),
              var(--shadow-sm);
}

/* Trigger button */
.dynamics-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: background var(--duration-fast);
}
.dynamics-trigger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 4%, transparent);
}
.dynamics-trigger:disabled {
  cursor: default;
  opacity: 0.6;
}
.dynamics-trigger__left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dynamics-trigger__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--accent-surface);
  color: var(--accent);
  flex-shrink: 0;
}
.dynamics-trigger--open .dynamics-trigger__icon {
  background: var(--accent);
  color: white;
}
.dynamics-trigger__title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-display);
  letter-spacing: -0.01em;
}
.dynamics-trigger__subtitle {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 1px;
}
.dynamics-trigger__chevron {
  color: var(--text-tertiary);
  transition: transform var(--duration-normal) var(--ease-out),
              color var(--duration-fast);
}
.dynamics-trigger__chevron--open {
  transform: rotate(90deg);
  color: var(--accent);
}

/* Expand transition */
.dynamics-expand-enter-active,
.dynamics-expand-leave-active {
  transition: all var(--duration-slow) var(--ease-out);
  overflow: hidden;
}
.dynamics-expand-enter-from,
.dynamics-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.dynamics-expand-enter-to,
.dynamics-expand-leave-from {
  opacity: 1;
  max-height: 600px;
}

/* Body */
.dynamics-body {
  border-top: 1px solid var(--border);
}
.dynamics-body__inner {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Custom toggle switch */
.dynamics-toggle {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background var(--duration-fast);
}
.dynamics-toggle:hover {
  background: color-mix(in srgb, var(--accent) 4%, transparent);
}
.dynamics-toggle--disabled {
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}
.dynamics-toggle__track {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--border);
  flex-shrink: 0;
  margin-top: 1px;
  transition: background var(--duration-normal) var(--ease-out);
}
.dynamics-toggle__track--on {
  background: var(--accent);
}
.dynamics-toggle__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: transform var(--duration-normal) var(--ease-spring);
}
.dynamics-toggle__thumb--on {
  transform: translateX(16px);
}
.dynamics-toggle__label {
  display: block;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-primary);
}
.dynamics-toggle__desc {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 1px;
  line-height: 1.4;
}

/* Integrators section */
.dynamics-integrators {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dynamics-integrators__divider {
  height: 1px;
  background: var(--border);
  margin: 2px 0;
}
.dynamics-integrators__grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Method card */
.dynamics-method {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-raised);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast);
}
.dynamics-method:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
  background: color-mix(in srgb, var(--accent) 3%, var(--surface-raised));
}
.dynamics-method--selected {
  border-color: var(--accent) !important;
  background: var(--accent-surface) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 20%, transparent);
}
.dynamics-method--disabled {
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}
.dynamics-method__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid var(--border);
  flex-shrink: 0;
  margin-top: 3px;
  transition: all var(--duration-fast);
}
.dynamics-method--selected .dynamics-method__dot {
  border-color: var(--accent);
  background: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-surface);
}
.dynamics-method__name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.dynamics-method__desc {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 1px;
  line-height: 1.4;
}

/* Param rows */
.dynamics-param {
  padding-top: 6px;
}
.dynamics-param__label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}
.dynamics-param__input {
  width: 140px;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid var(--border);
  background: var(--surface-raised);
  color: var(--text-primary);
  font-family: var(--font-mono);
  transition: border-color var(--duration-fast);
}
.dynamics-param__input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 15%, transparent);
}
.dynamics-param__chips {
  display: flex;
  gap: 4px;
}

/* Chip buttons */
.dynamics-chip {
  padding: 4px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-mono);
  border: 1px solid var(--border);
  background: var(--surface-raised);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast);
}
.dynamics-chip:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
}
.dynamics-chip--active {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: white !important;
  box-shadow: 0 1px 3px color-mix(in srgb, var(--accent) 30%, transparent);
}
</style>
