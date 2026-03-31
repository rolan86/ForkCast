<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import * as simApi from '@/api/simulations.js'
import AgentRoster from '@/components/interact/AgentRoster.vue'
import InterviewMode from '@/components/interact/InterviewMode.vue'
import PanelMode from '@/components/interact/PanelMode.vue'
import SurveyMode from '@/components/interact/SurveyMode.vue'
import DebateMode from '@/components/interact/DebateMode.vue'
import ReportChatMode from '@/components/interact/ReportChatMode.vue'
import { suggestAgents as fetchSuggestions } from '@/api/interact.js'
import { listReports } from '@/api/reports.js'

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
const simulation = ref(null)
const loading = ref(false)

const agents = computed(() => {
  const sim = simulation.value
  if (!sim?.config?.profiles) return []
  return sim.config.profiles
})

const selectedAgent = computed(() => {
  if (selectedAgentIds.value.length === 0) return null
  return agents.value.find(a => a.agent_id === selectedAgentIds.value[0]) || null
})

const simulationId = computed(() => simulation.value?.id || '')
const simState = computed(() => simulation.value?.status || '')
const hasReport = computed(() => simulation.value?.has_report || false)
const currentReportId = ref('')

async function loadSimulation() {
  loading.value = true
  try {
    await store.fetchSimulations()
    const sims = store.projectSimulations
    if (sims.length) {
      // Pick the most relevant simulation: prefer prepared/completed over created
      const usable = sims.find(s => ['prepared', 'completed'].includes(s.status)) || sims[0]
      const sim = await simApi.getSimulation(usable.id)
      simulation.value = sim
    }
  } catch (e) {
    console.error('Failed to load simulation for Interact tab:', e)
  } finally {
    loading.value = false
  }
}

async function fetchLatestReportId() {
  if (!simulationId.value) return
  try {
    const reports = await listReports(simulationId.value)
    const completed = reports.filter(r => r.status === 'completed')
    if (completed.length) {
      currentReportId.value = completed[0].id
    }
  } catch { /* no reports yet */ }
}

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
  if (modeId === 'report') fetchLatestReportId()
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

onMounted(async () => {
  await loadSimulation()
  if (route.query.agent) {
    selectedAgentIds.value = [parseInt(route.query.agent)]
  }
  if (activeMode.value === 'report') {
    fetchLatestReportId()
  }
})
</script>

<template>
  <!-- Loading state -->
  <div v-if="loading" :style="{
    display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%',
    color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '14px',
  }">
    Loading simulation data...
  </div>

  <!-- No simulation available -->
  <div v-else-if="!simulation" :style="{
    display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%',
    flexDirection: 'column', gap: '8px',
    color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)',
  }">
    <div :style="{ fontSize: '16px', fontWeight: 600, fontFamily: 'var(--font-display)' }">No simulation available</div>
    <div :style="{ fontSize: '13px' }">Prepare a simulation in the Simulations tab to start interacting with agents.</div>
  </div>

  <!-- Main layout -->
  <div v-else :style="{ display: 'flex', height: '100%' }">
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

      <PanelMode
        v-else-if="activeMode === 'panel'"
        :simulation-id="simulationId"
        :agents="agents"
        :selected-agent-ids="selectedAgentIds"
      />

      <SurveyMode
        v-else-if="activeMode === 'survey'"
        :simulation-id="simulationId"
        :agents="agents"
        :selected-agent-ids="selectedAgentIds"
      />

      <DebateMode
        v-else-if="activeMode === 'debate'"
        :simulation-id="simulationId"
        :agents="agents"
      />

      <ReportChatMode
        v-else-if="activeMode === 'report'"
        :report-id="currentReportId"
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
