<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import StepIndicator from './StepIndicator.vue'
import AgentTicker from './AgentTicker.vue'
import { useConstellationCanvas } from '@/composables/useConstellationCanvas.js'

const GRAPH_COLORS = ['#00d4ff', '#818cf8', '#a855f7', '#34d399', '#fbbf24']

const props = defineProps({
  steps: { type: Array, required: true },
  currentStage: { type: String, default: '' },
  progress: { type: Object, default: () => ({ current: null, total: null }) },
  logEntries: { type: Array, default: () => [] },
  error: { type: String, default: '' },
  errorType: { type: String, default: '' },
  resumable: { type: Boolean, default: false },
  agentData: { type: Object, default: null },
})

const emit = defineEmits(['cancel', 'retry', 'resume', 'startOver', 'morphComplete'])

const canvasRef = ref(null)
const tickerRef = ref(null)
const constellation = useConstellationCanvas()
let seedsAdded = false

const stepStatuses = ref(
  props.steps.map(() => 'pending')
)

// Compute step statuses from currentStage
watch(() => props.currentStage, (stage) => {
  let foundActive = false
  stepStatuses.value = props.steps.map(step => {
    if (foundActive) return 'pending'
    if (step.stageNames.includes(stage)) {
      foundActive = true
      return 'active'
    }
    return 'done'
  })

  // Stage-specific constellation behavior
  if (stage === 'loading_graph' && !seedsAdded) {
    seedsAdded = true
    const count = 8 + Math.floor(Math.random() * 5)
    for (let i = 0; i < count; i++) {
      setTimeout(() => {
        constellation.addSeedNode(GRAPH_COLORS[i % GRAPH_COLORS.length])
      }, i * 200)
    }
  }

  if (stage === 'generating_config') {
    constellation.activateNetwork()
  }
}, { immediate: true })

// Add agent nodes as profiles arrive
watch(() => props.progress.current, (current) => {
  if (props.currentStage === 'generating_profiles' && current) {
    constellation.addAgentNode(`agent_${current}`)
  }
})

// Push agent data to ticker
watch(() => props.agentData, (data) => {
  if (data && tickerRef.value) {
    tickerRef.value.push({
      name: data.agent_name || data.name,
      bio: data.agent_bio || data.bio || '',
    })
  }
}, { deep: true })

// Morph on completion
watch(() => props.currentStage, (stage) => {
  if (stage === 'result') {
    const agentCount = constellation.nodes.value.filter(n => n.type === 'agent').length
    if (agentCount > 0 && canvasRef.value) {
      const rect = canvasRef.value.getBoundingClientRect()
      const targets = constellation.computeGridTargets(rect.width, rect.height, agentCount)
      constellation.flashAndMorph(targets)
    } else {
      emit('morphComplete')
    }
  }
})

constellation.onMorphComplete(() => {
  emit('morphComplete')
})

onMounted(() => {
  if (canvasRef.value) {
    constellation.init(canvasRef.value)
  }
})

onUnmounted(() => {
  constellation.destroy()
})

const tickerFallback = ref('')
watch(() => [props.currentStage, props.progress], ([stage, prog]) => {
  if (stage && prog.current) {
    tickerFallback.value = `${stage.replace(/_/g, ' ')} (${prog.current}/${prog.total})`
  } else if (stage) {
    tickerFallback.value = stage.replace(/_/g, ' ')
  }
}, { deep: true })

// Error display
const errorBorderColor = ref('var(--danger)')
watch(() => props.errorType, (type) => {
  if (type === 'rate_limited') errorBorderColor.value = 'var(--warning)'
  else if (type === 'credits_exhausted') errorBorderColor.value = '#f97316'
  else errorBorderColor.value = 'var(--danger)'
})
</script>

<template>
  <div class="prepare-visualizer">
    <!-- Step Indicator -->
    <div class="prepare-visualizer__steps">
      <StepIndicator
        :steps="steps.map((s, i) => ({ ...s, status: stepStatuses[i] }))"
        mode="pipeline"
      />
    </div>

    <!-- Canvas + Ticker container -->
    <div class="prepare-visualizer__stage">
      <canvas ref="canvasRef" class="prepare-visualizer__canvas"></canvas>

      <AgentTicker
        ref="tickerRef"
        :fallbackText="tickerFallback"
        class="prepare-visualizer__ticker"
      />

      <!-- Error overlay -->
      <div v-if="error" class="prepare-visualizer__error">
        <div
          class="prepare-visualizer__error-box"
          :style="{ borderColor: errorBorderColor }"
        >
          <p class="prepare-visualizer__error-text">{{ error }}</p>
          <div class="prepare-visualizer__error-actions">
            <button
              v-if="resumable"
              class="prepare-visualizer__btn prepare-visualizer__btn--primary"
              @click="$emit('resume')"
            >Resume</button>
            <button
              v-if="!resumable"
              class="prepare-visualizer__btn prepare-visualizer__btn--primary"
              @click="$emit('retry')"
            >Retry</button>
            <button
              class="prepare-visualizer__btn prepare-visualizer__btn--secondary"
              @click="$emit('startOver')"
            >Start Over</button>
            <button
              data-testid="cancel-btn"
              class="prepare-visualizer__btn prepare-visualizer__btn--secondary"
              @click="$emit('cancel')"
            >Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prepare-visualizer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
}
.prepare-visualizer__steps {
  padding: 16px 16px 12px;
}
.prepare-visualizer__stage {
  flex: 1;
  position: relative;
  background: var(--data-bg);
  border-radius: 10px;
  overflow: hidden;
  margin: 0 16px 16px;
  border: 1px solid var(--data-border);
}
.prepare-visualizer__canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.prepare-visualizer__ticker {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
}

/* Error overlay */
.prepare-visualizer__error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(9, 9, 11, 0.8);
  z-index: 10;
}
.prepare-visualizer__error-box {
  max-width: 400px;
  padding: 20px;
  border-radius: 10px;
  border: 1px solid;
  background: var(--data-bg-raised);
}
.prepare-visualizer__error-text {
  color: var(--data-text);
  font-size: 13px;
  margin-bottom: 16px;
}
.prepare-visualizer__error-actions {
  display: flex;
  gap: 8px;
}
.prepare-visualizer__btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  cursor: pointer;
}
.prepare-visualizer__btn--primary {
  background: var(--accent);
  color: white;
}
.prepare-visualizer__btn--secondary {
  background: transparent;
  border: 1px solid var(--data-border);
  color: var(--data-text-muted);
}
</style>
