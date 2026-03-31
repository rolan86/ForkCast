<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import AgentRoster from '@/components/interact/AgentRoster.vue'
import InterviewMode from '@/components/interact/InterviewMode.vue'
import { suggestAgents as fetchSuggestions } from '@/api/interact.js'

const route = useRoute()
const store = useProjectStore()

const MODES = [
  { id: 'interview', label: 'Interview' },
  { id: 'panel', label: 'Panel' },
  { id: 'survey', label: 'Survey' },
  { id: 'debate', label: 'Debate' },
  { id: 'report', label: 'Report' },
]

const activeMode = ref(route.query.mode || 'interview')
const selectedAgentIds = ref([])
const suggestions = ref([])
const currentTopic = ref('')

const agents = computed(() => {
  const sim = store.currentSimulation
  if (!sim?.agents) return []
  return sim.agents
})

const selectedAgent = computed(() => {
  if (selectedAgentIds.value.length === 0) return null
  return agents.value.find(a => a.agent_id === selectedAgentIds.value[0]) || null
})

const currentSimulation = computed(() => store.currentSimulation)
const simulationId = computed(() => currentSimulation.value?.id || '')
const simState = computed(() => currentSimulation.value?.status || '')
const hasReport = computed(() => store.currentSimulation?.has_report || false)

function isModeAvailable(modeId) {
  if (modeId === 'report') return hasReport.value
  return ['prepared', 'completed'].includes(simState.value)
}

function modeTooltip(modeId) {
  if (isModeAvailable(modeId)) return ''
  if (modeId === 'report') return 'Generate a report first'
  return 'Prepare a simulation first'
}

function selectMode(modeId) {
  if (!isModeAvailable(modeId)) return
  activeMode.value = modeId
  selectedAgentIds.value = []
  suggestions.value = []
}

function onAgentSelect(agentId) {
  if (activeMode.value === 'interview') {
    selectedAgentIds.value = [agentId]
  } else {
    selectedAgentIds.value.push(agentId)
  }
}

function onAgentDeselect(agentId) {
  selectedAgentIds.value = selectedAgentIds.value.filter(id => id !== agentId)
}

async function onSuggest() {
  if (!simulationId.value) return
  try {
    const result = await fetchSuggestions(simulationId.value, currentTopic.value || 'general discussion')
    suggestions.value = result.suggestions || []
  } catch (e) {
    console.error('Suggest failed:', e)
  }
}

onMounted(() => {
  if (route.query.agent) {
    selectedAgentIds.value = [parseInt(route.query.agent)]
  }
})
</script>

<template>
  <div :style="{ display: 'flex', height: '100%' }">
    <!-- Sidebar -->
    <div :style="{
      width: '260px',
      backgroundColor: 'var(--interact-sidebar-bg)',
      color: 'var(--interact-sidebar-text)',
      display: 'flex', flexDirection: 'column',
      borderRight: '1px solid var(--border)',
      overflow: 'hidden',
    }">
      <!-- Mode selector -->
      <div :style="{ padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.08)' }">
        <div :style="{
          fontFamily: 'var(--font-mono)', fontSize: '10px',
          textTransform: 'uppercase', letterSpacing: '1px',
          color: 'var(--text-tertiary)', marginBottom: '10px', fontWeight: 600,
        }">
          Mode
        </div>
        <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '6px' }">
          <button
            v-for="mode in MODES"
            :key="mode.id"
            @click="selectMode(mode.id)"
            :disabled="!isModeAvailable(mode.id)"
            :title="modeTooltip(mode.id)"
            :style="{
              padding: '5px 12px',
              borderRadius: '14px',
              border: 'none',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              fontWeight: activeMode === mode.id ? 700 : 500,
              cursor: isModeAvailable(mode.id) ? 'pointer' : 'not-allowed',
              backgroundColor: activeMode === mode.id
                ? 'var(--interact-pill-active)'
                : 'rgba(255,255,255,0.06)',
              color: activeMode === mode.id ? '#fff' : 'var(--text-tertiary)',
              opacity: isModeAvailable(mode.id) ? 1 : 0.3,
              boxShadow: activeMode === mode.id ? 'var(--interact-pill-glow)' : 'none',
              transition: 'all var(--duration-fast) ease',
            }"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>

      <!-- Agent roster -->
      <div :style="{ flex: 1, overflowY: 'auto', padding: '12px' }">
        <div :style="{
          fontFamily: 'var(--font-mono)', fontSize: '10px',
          textTransform: 'uppercase', letterSpacing: '1px',
          color: 'var(--text-tertiary)', marginBottom: '10px', fontWeight: 600,
        }">
          Agents
        </div>
        <AgentRoster
          :agents="agents"
          :selected-ids="selectedAgentIds"
          :multi-select="['panel', 'survey'].includes(activeMode)"
          :suggestions="suggestions"
          @select="onAgentSelect"
          @deselect="onAgentDeselect"
          @suggest="onSuggest"
        />
      </div>
    </div>

    <!-- Main content area -->
    <div :style="{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <InterviewMode
        v-if="activeMode === 'interview'"
        :simulation-id="simulationId"
        :agent="selectedAgent"
      />

      <div
        v-else
        :style="{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)',
        }"
      >
        {{ activeMode }} mode — coming soon
      </div>
    </div>
  </div>
</template>
