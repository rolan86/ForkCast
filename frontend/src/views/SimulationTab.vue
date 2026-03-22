<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import * as simApi from '@/api/simulations.js'
import EmptyState from '@/components/EmptyState.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import StatCard from '@/components/StatCard.vue'
import LiveFeed from '@/components/LiveFeed.vue'
import AgentAvatar from '@/components/AgentAvatar.vue'
import PlatformBadge from '@/components/PlatformBadge.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'

const route = useRoute()
const store = useProjectStore()
const projectId = computed(() => route.params.id)

const viewState = ref('empty')
const prepareError = ref('')
const runError = ref('')
const showStopModal = ref(false)
const currentSimId = ref(null)
const simConfig = ref(null)
const agents = ref([])
const showAllAgents = ref(false)
const activePlatformTab = ref('twitter')
const expandedRunId = ref(null)

let sseConnection = null

const PREPARE_STEPS = [
  { label: 'Loading graph', stageNames: ['loading_graph'] },
  { label: 'Generating profiles', stageNames: ['generating_profiles'] },
  { label: 'Generating config', stageNames: ['generating_config', 'result'] },
]

onMounted(async () => {
  await store.fetchSimulations()
  const sims = store.projectSimulations
  if (!sims.length) {
    viewState.value = 'empty'
  } else {
    const latest = sims[0]
    currentSimId.value = latest.id
    if (latest.status === 'preparing') {
      viewState.value = 'preparing'
      connectPrepareSSE(latest.id)
    } else if (latest.status === 'prepared') {
      await loadPreparedState(latest.id)
    } else if (latest.status === 'running') {
      viewState.value = 'running'
      connectRunSSE(latest.id)
    } else {
      viewState.value = 'completed'
    }
  }
})

onUnmounted(() => {
  sseConnection?.close()
})

async function prepareSimulation() {
  prepareError.value = ''
  viewState.value = 'preparing'
  store.resetSimPrepareProgress()

  try {
    const sim = await simApi.createSimulation(projectId.value)
    currentSimId.value = sim.id
    await simApi.prepareSim(sim.id)
    connectPrepareSSE(sim.id)
  } catch (e) {
    prepareError.value = e.message
  }
}

function connectPrepareSSE(simId) {
  sseConnection = simApi.streamPrepare(simId, {
    onMessage(data) {
      store.updateSimPrepareProgress(data)
    },
    onError(message) {
      prepareError.value = message
    },
    async onComplete() {
      await loadPreparedState(simId)
    },
    onDisconnect() {
      if (!prepareError.value) prepareError.value = 'Connection lost'
    },
  })
}

async function loadPreparedState(simId) {
  const sim = await simApi.getSimulation(simId)
  currentSimId.value = simId
  simConfig.value = sim.config_json ? JSON.parse(sim.config_json) : null
  agents.value = simConfig.value?.profiles || []
  viewState.value = 'prepared'
}

async function startSimulation() {
  viewState.value = 'running'
  store.resetSimRunProgress()
  try {
    await simApi.startSim(currentSimId.value)
    connectRunSSE(currentSimId.value)
  } catch (e) {
    runError.value = e.message
  }
}

function connectRunSSE(simId) {
  sseConnection = simApi.streamSimRun(simId, {
    onMessage(data) {
      store.updateSimRunProgress(data)
      if (data.stage === 'action') {
        store.addLiveFeedAction(data)
      }
    },
    onError(message) {
      runError.value = message
    },
    async onComplete() {
      await store.fetchSimulations()
      viewState.value = 'completed'
    },
    onDisconnect() {
      if (!runError.value) runError.value = 'Connection lost'
    },
  })
}

async function stopSimulation() {
  showStopModal.value = false
  await simApi.stopSim(currentSimId.value)
}

function newSimulation() {
  viewState.value = 'empty'
}

const graphBuilt = computed(() => store.currentGraph?.status === 'complete' || store.currentGraph?.status === 'built')
const sims = computed(() => store.projectSimulations)
const runProgress = computed(() => store.simRunProgress)
const platforms = computed(() => {
  if (!simConfig.value?.platforms) return ['twitter']
  return simConfig.value.platforms
})
const filteredActions = computed(() => {
  if (platforms.value.length <= 1) return store.liveFeedActions
  return store.liveFeedActions.filter(a => a.platform === activePlatformTab.value)
})
const actionTypesCount = computed(() => {
  const types = new Set(store.liveFeedActions.map(a => a.action_type))
  return types.size
})
function platformActionCount(p) {
  return store.liveFeedActions.filter(a => a.platform === p).length
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}
</script>

<template>
  <!-- Empty -->
  <div v-if="viewState === 'empty'" class="p-6">
    <EmptyState
      icon="Play"
      title="No simulations yet"
      description="Simulations create AI agents from your knowledge graph and run them on a simulated social platform."
      actionLabel="Prepare Simulation"
      :disabled="!graphBuilt"
      :disabledTooltip="!graphBuilt ? 'Build a knowledge graph first' : ''"
      @action="prepareSimulation"
    />
  </div>

  <!-- Preparing -->
  <div v-else-if="viewState === 'preparing'" class="p-6">
    <ProgressPanel
      title="Preparing Simulation..."
      :steps="PREPARE_STEPS"
      :currentStage="store.simPrepareProgress?.stage || ''"
      :progress="{ current: store.simPrepareProgress?.current, total: store.simPrepareProgress?.total }"
      :logEntries="store.simPrepareProgress?.logEntries || []"
      :error="prepareError"
      @cancel="viewState = 'empty'"
      @retry="prepareSimulation"
    />
  </div>

  <!-- Prepared -->
  <div v-else-if="viewState === 'prepared'" class="p-6 space-y-6">
    <div class="flex gap-3">
      <div v-for="platform in (simConfig?.platforms || ['twitter'])" :key="platform">
        <PlatformBadge :platform="platform" size="md" />
      </div>
      <StatCard label="Rounds" :value="simConfig?.rounds || 12" class="flex-1" />
      <StatCard label="Agents" :value="agents.length" class="flex-1" />
    </div>

    <div>
      <p class="text-xs uppercase tracking-wider mb-3" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }">Agent Roster</p>
      <div class="grid grid-cols-3 gap-3">
        <div
          v-for="agent in (showAllAgents ? agents : agents.slice(0, 6))"
          :key="agent.username"
          class="rounded-lg border p-3"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }"
        >
          <div class="flex items-center gap-2 mb-1.5">
            <AgentAvatar :name="agent.name || agent.username" size="md" />
            <span class="text-sm font-semibold truncate" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }">@{{ agent.username }}</span>
          </div>
          <p class="text-xs line-clamp-2" :style="{ color: 'var(--text-secondary)' }">{{ agent.persona || agent.bio }}</p>
        </div>
      </div>
      <button
        v-if="agents.length > 6 && !showAllAgents"
        class="mt-2 text-sm"
        :style="{ color: 'var(--accent)' }"
        @click="showAllAgents = true"
      >+ {{ agents.length - 6 }} more agents</button>
    </div>

    <div class="flex gap-3 justify-end">
      <button
        class="px-4 py-2 rounded-lg text-sm border"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
        @click="prepareSimulation"
      >Re-prepare</button>
      <button
        class="px-5 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--success)' }"
        @click="startSimulation"
      >Run Simulation</button>
    </div>
  </div>

  <!-- Running -->
  <div v-else-if="viewState === 'running'" class="flex flex-col h-full">
    <div class="data-panel px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-6">
        <div>
          <span class="text-3xl font-bold" :style="{ fontFamily: 'var(--font-display)', color: 'var(--data-text)' }">
            {{ runProgress?.currentRound || 0 }}/{{ runProgress?.totalRounds || '?' }}
          </span>
          <span class="text-xs uppercase tracking-wider ml-2" :style="{ color: 'var(--data-text-muted)', fontFamily: 'var(--font-mono)' }">Rounds</span>
        </div>
        <div class="text-sm" :style="{ color: 'var(--data-text-muted)', fontFamily: 'var(--font-mono)' }">
          {{ store.liveFeedActions.length }} actions
        </div>
      </div>
      <button
        class="px-4 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--danger)' }"
        @click="showStopModal = true"
      >Stop</button>
    </div>

    <div class="grid grid-cols-3 gap-3 px-4 pt-4">
      <StatCard label="Actions" :value="store.liveFeedActions.length" icon="Zap" />
      <StatCard label="Agents" :value="agents.length || '—'" icon="Users" />
      <StatCard label="Action Types" :value="actionTypesCount" icon="Layers" />
    </div>

    <div v-if="platforms.length > 1" class="flex gap-1 px-4 pt-3">
      <button
        v-for="p in platforms"
        :key="p"
        class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
        :style="{
          backgroundColor: activePlatformTab === p ? 'var(--accent-surface)' : 'transparent',
          color: activePlatformTab === p ? 'var(--accent)' : 'var(--text-secondary)',
        }"
        @click="activePlatformTab = p"
      >
        <PlatformBadge :platform="p" size="sm" />
        <span class="ml-1 text-xs" :style="{ fontFamily: 'var(--font-mono)' }">{{ platformActionCount(p) }}</span>
      </button>
    </div>

    <div class="flex-1 p-4">
      <LiveFeed :actions="filteredActions" :platform="activePlatformTab" />
    </div>

    <ConfirmModal
      v-if="showStopModal"
      title="Stop Simulation?"
      message="The simulation will stop after the current round completes."
      confirmLabel="Stop"
      variant="danger"
      @confirm="stopSimulation"
      @cancel="showStopModal = false"
    />
  </div>

  <!-- Completed -->
  <div v-else class="p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">Simulation Results</h3>
      <button
        class="px-4 py-2 rounded-lg text-sm border"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
        @click="newSimulation"
      >+ New Simulation</button>
    </div>

    <div class="rounded-xl border overflow-hidden" :style="{ borderColor: 'var(--border)' }">
      <div class="flex px-4 py-2 text-xs uppercase tracking-wider" :style="{ backgroundColor: 'var(--surface-sunken)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">
        <div class="w-16">Run</div>
        <div class="flex-1">Platforms</div>
        <div class="w-40">Date</div>
        <div class="w-20">Rounds</div>
        <div class="w-20">Actions</div>
        <div class="w-24">Status</div>
      </div>
      <div
        v-for="(sim, i) in sims"
        :key="sim.id"
      >
        <div
          class="flex px-4 py-3 items-center cursor-pointer transition-colors"
          :style="{
            backgroundColor: i === 0 ? 'var(--accent-surface)' : 'var(--surface-raised)',
            borderLeft: i === 0 ? '3px solid var(--accent)' : 'none',
          }"
          @click="expandedRunId = expandedRunId === sim.id ? null : sim.id"
        >
          <div class="w-16 text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">#{{ sims.length - i }}</div>
          <div class="flex-1 flex gap-1">
            <PlatformBadge v-for="p in (JSON.parse(sim.platforms || '[]'))" :key="p" :platform="p" size="sm" />
          </div>
          <div class="w-40 text-xs" :style="{ color: 'var(--text-secondary)' }">{{ formatDate(sim.created_at) }}</div>
          <div class="w-20 text-sm" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }">{{ sim.rounds_completed || '?' }}/{{ sim.total_rounds || '?' }}</div>
          <div class="w-20 text-sm font-semibold" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }">{{ sim.actions_count || '-' }}</div>
          <div class="w-24">
            <span
              class="text-xs px-2 py-0.5 rounded font-medium"
              :style="{
                backgroundColor: sim.status === 'completed' ? '#dcfce7' : sim.status === 'stopped' ? '#fef3c7' : '#e4e4e7',
                color: sim.status === 'completed' ? '#16a34a' : sim.status === 'stopped' ? '#d97706' : '#71717a',
              }"
            >{{ sim.status === 'completed' ? 'Complete' : sim.status === 'stopped' ? 'Stopped' : sim.status }}</span>
          </div>
        </div>
        <div
          v-if="expandedRunId === sim.id"
          class="px-8 py-3 border-t"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-sunken)' }"
        >
          <button
            class="px-4 py-1.5 rounded-md text-xs font-medium text-white opacity-50 cursor-not-allowed"
            :style="{ backgroundColor: 'var(--accent)' }"
            disabled
            title="Available in Phase 7b"
          >Generate Report</button>
        </div>
      </div>
    </div>
  </div>
</template>
