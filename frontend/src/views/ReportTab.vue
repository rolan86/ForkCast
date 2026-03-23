<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import * as reportApi from '@/api/reports.js'
import EmptyState from '@/components/EmptyState.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import PlatformBadge from '@/components/PlatformBadge.vue'

const route = useRoute()
const store = useProjectStore()
const projectId = computed(() => route.params.id)

// State: 'empty' | 'select' | 'generating' | 'viewing' | 'chatting'
const viewState = ref('empty')
const reports = ref([])
const currentReport = ref(null)
const generateError = ref('')
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)

let sseConnection = null

const GENERATE_STEPS = [
  { label: 'Loading context', stageNames: ['loading'] },
  { label: 'Analyzing data', stageNames: ['thinking', 'tool_use'] },
  { label: 'Writing report', stageNames: ['forcing', 'complete', 'result'] },
]

const completedSims = computed(() =>
  store.projectSimulations.filter(s => s.status === 'completed')
)

onMounted(async () => {
  await store.fetchSimulations()
  // Load existing reports for this project's simulations
  await loadReports()
  if (reports.value.length) {
    viewState.value = 'select'
  } else if (completedSims.value.length) {
    viewState.value = 'select'
  } else {
    viewState.value = 'empty'
  }
})

onUnmounted(() => {
  if (sseConnection) {
    sseConnection.close()
    sseConnection = null
  }
})

async function loadReports() {
  const allReports = []
  for (const sim of store.projectSimulations) {
    try {
      const simReports = await reportApi.listReports(sim.id)
      allReports.push(...simReports)
    } catch { /* skip */ }
  }
  reports.value = allReports.sort((a, b) =>
    new Date(b.created_at) - new Date(a.created_at)
  )
}

async function generateFromSim(simId) {
  generateError.value = ''
  viewState.value = 'generating'
  try {
    const result = await reportApi.generateReport(simId)
    connectGenerateSSE(result.report_id)
  } catch (e) {
    generateError.value = e.message
  }
}

function connectGenerateSSE(reportId) {
  sseConnection = reportApi.streamGenerate(reportId, {
    onMessage(data) {
      store.updateReportProgress?.(data)
      if (!store.reportProgress) {
        store.reportProgress = { stage: '', logEntries: [] }
      }
      store.reportProgress.stage = data.stage
      store.reportProgress.logEntries = store.reportProgress.logEntries || []
      store.reportProgress.logEntries.push({
        message: data.message || data.stage,
        type: 'progress',
      })
    },
    onError(message) {
      generateError.value = message
    },
    async onComplete() {
      await loadReports()
      if (reports.value.length) {
        currentReport.value = await reportApi.getReport(reports.value[0].id)
        viewState.value = 'viewing'
      }
    },
    onDisconnect() {
      if (!generateError.value) generateError.value = 'Connection lost'
    },
    onReconnect() {
      generateError.value = ''
    },
  })
}

async function viewReport(report) {
  currentReport.value = await reportApi.getReport(report.id)
  chatMessages.value = []
  viewState.value = 'viewing'
}

function backToList() {
  currentReport.value = null
  viewState.value = 'select'
}

async function sendChat() {
  if (!chatInput.value.trim() || chatLoading.value) return
  const message = chatInput.value.trim()
  chatInput.value = ''
  chatMessages.value.push({ role: 'user', content: message })
  chatLoading.value = true

  let assistantText = ''
  chatMessages.value.push({ role: 'assistant', content: '' })
  const assistantIdx = chatMessages.value.length - 1

  try {
    await reportApi.chatWithReport(currentReport.value.id, message, (eventType, data) => {
      if (eventType === 'text_delta') {
        assistantText += typeof data === 'string' ? data : (data.text || '')
        chatMessages.value[assistantIdx].content = assistantText
      }
    })
  } catch (e) {
    chatMessages.value[assistantIdx].content = `Error: ${e.message}`
  } finally {
    chatLoading.value = false
  }
}

function exportReport() {
  if (!currentReport.value) return
  window.open(reportApi.exportReportUrl(currentReport.value.id), '_blank')
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })
}

function renderMarkdown(md) {
  if (!md) return '<p style="color: var(--text-tertiary); font-style: italic;">No content</p>'
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3 style="font-size: 1.1rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size: 1.25rem; font-weight: 700; margin-top: 2rem; margin-bottom: 0.75rem;">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size: 1.5rem; font-weight: 800; margin-top: 2rem; margin-bottom: 1rem;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li style="margin-left: 1.5rem;">$1</li>')
    .replace(/\n\n/g, '</p><p style="margin-bottom: 0.75rem;">')
    .replace(/^(?!<[hlo])(.+)/gm, '<p style="margin-bottom: 0.75rem;">$1</p>')
}
</script>

<template>
  <!-- Empty — no completed simulations -->
  <div v-if="viewState === 'empty'" class="p-6">
    <EmptyState
      icon="FileText"
      title="No reports yet"
      description="Complete a simulation first, then generate a prediction report from its results."
    />
  </div>

  <!-- Select — pick a simulation or view existing reports -->
  <div v-else-if="viewState === 'select'" class="p-6 space-y-6">
    <!-- Existing reports -->
    <div v-if="reports.length">
      <h3 class="text-xs uppercase tracking-wider mb-3" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">
        Reports
      </h3>
      <div class="space-y-2">
        <div
          v-for="report in reports"
          :key="report.id"
          class="flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }"
          @click="viewReport(report)"
          @mouseenter="$el.style.borderColor = 'var(--accent)'"
          @mouseleave="$el.style.borderColor = 'var(--border)'"
        >
          <div>
            <span class="text-sm font-medium" :style="{ color: 'var(--text-primary)' }">
              Report #{{ report.id.slice(-6) }}
            </span>
            <span class="text-xs ml-2" :style="{ color: 'var(--text-tertiary)' }">
              {{ formatDate(report.completed_at || report.created_at) }}
            </span>
          </div>
          <span
            class="text-xs px-2 py-0.5 rounded font-medium"
            :style="{
              backgroundColor: report.status === 'completed' ? '#dcfce7' : '#fef3c7',
              color: report.status === 'completed' ? '#16a34a' : '#d97706',
            }"
          >{{ report.status }}</span>
        </div>
      </div>
    </div>

    <!-- Generate from completed simulation -->
    <div v-if="completedSims.length">
      <h3 class="text-xs uppercase tracking-wider mb-3" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">
        Generate New Report
      </h3>
      <div class="space-y-2">
        <div
          v-for="sim in completedSims"
          :key="sim.id"
          class="flex items-center justify-between p-3 rounded-lg border"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }"
        >
          <div class="flex items-center gap-3">
            <div class="flex gap-1">
              <PlatformBadge v-for="p in (Array.isArray(sim.platforms) ? sim.platforms : [])" :key="p" :platform="p" size="sm" />
            </div>
            <span class="text-sm" :style="{ color: 'var(--text-primary)' }">
              Simulation #{{ sim.id.slice(-6) }}
            </span>
            <span class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
              {{ sim.actions_count || 0 }} actions
            </span>
          </div>
          <button
            class="px-4 py-1.5 rounded-md text-xs font-medium text-white"
            :style="{ backgroundColor: 'var(--accent)' }"
            @click="generateFromSim(sim.id)"
          >Generate Report</button>
        </div>
      </div>
    </div>

    <div v-if="!completedSims.length && !reports.length">
      <EmptyState
        icon="FileText"
        title="No completed simulations"
        description="Run a simulation to completion, then generate a report."
      />
    </div>
  </div>

  <!-- Generating -->
  <div v-else-if="viewState === 'generating'" class="p-6">
    <ProgressPanel
      title="Generating Report..."
      :steps="GENERATE_STEPS"
      :currentStage="store.reportProgress?.stage || ''"
      :logEntries="store.reportProgress?.logEntries || []"
      :error="generateError"
      @cancel="viewState = 'select'"
      @retry="() => { viewState = 'select' }"
    />
  </div>

  <!-- Viewing report -->
  <div v-else-if="viewState === 'viewing' || viewState === 'chatting'" class="flex flex-col h-full">
    <!-- Header -->
    <div class="px-6 py-4 flex items-center justify-between" :style="{ borderBottom: '1px solid var(--border)' }">
      <div class="flex items-center gap-3">
        <button
          class="text-sm"
          :style="{ color: 'var(--text-secondary)' }"
          @click="backToList"
        >&larr; Back</button>
        <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }">
          Report #{{ currentReport?.id?.slice(-6) }}
        </h3>
        <span
          class="text-xs px-2 py-0.5 rounded font-medium"
          :style="{ backgroundColor: '#dcfce7', color: '#16a34a' }"
        >{{ currentReport?.status }}</span>
      </div>
      <div class="flex gap-2">
        <button
          class="px-3 py-1.5 rounded-md text-xs font-medium border"
          :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
          @click="viewState = viewState === 'chatting' ? 'viewing' : 'chatting'"
        >{{ viewState === 'chatting' ? 'View Report' : 'Chat' }}</button>
        <button
          class="px-3 py-1.5 rounded-md text-xs font-medium border"
          :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
          @click="exportReport"
        >Export</button>
      </div>
    </div>

    <!-- Report content -->
    <div v-if="viewState === 'viewing'" class="flex-1 overflow-auto p-6">
      <div
        class="prose max-w-none"
        :style="{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }"
        v-html="renderMarkdown(currentReport?.content_markdown || '')"
      />
      <div v-if="currentReport?.tool_history?.length" class="mt-8 pt-4" :style="{ borderTop: '1px solid var(--border)' }">
        <h4 class="text-xs uppercase tracking-wider mb-2" :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">
          Tool Usage ({{ currentReport.tool_history.length }} calls)
        </h4>
        <div class="space-y-1">
          <div v-for="(t, i) in currentReport.tool_history.slice(0, 10)" :key="i" class="text-xs" :style="{ color: 'var(--text-secondary)' }">
            Round {{ t.round }}: <span :style="{ fontFamily: 'var(--font-mono)' }">{{ t.tool }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat -->
    <div v-else-if="viewState === 'chatting'" class="flex-1 flex flex-col overflow-hidden">
      <div class="flex-1 overflow-auto p-6 space-y-4">
        <div v-if="!chatMessages.length" class="text-center py-12">
          <p class="text-sm" :style="{ color: 'var(--text-tertiary)' }">Ask questions about this report. The AI has full context of the simulation data.</p>
        </div>
        <div
          v-for="(msg, i) in chatMessages"
          :key="i"
          class="max-w-[80%] p-3 rounded-lg text-sm"
          :class="msg.role === 'user' ? 'ml-auto' : 'mr-auto'"
          :style="{
            backgroundColor: msg.role === 'user' ? 'var(--accent-surface)' : 'var(--surface-sunken)',
            color: 'var(--text-primary)',
          }"
        >
          <div style="white-space: pre-wrap">{{ msg.content }}</div>
        </div>
        <div v-if="chatLoading" class="text-xs animate-pulse" :style="{ color: 'var(--text-tertiary)' }">Thinking...</div>
      </div>
      <div class="p-4 flex gap-2" :style="{ borderTop: '1px solid var(--border)' }">
        <input
          v-model="chatInput"
          class="flex-1 px-3 py-2 rounded-lg text-sm border"
          :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)', color: 'var(--text-primary)' }"
          placeholder="Ask about this report..."
          @keydown.enter="sendChat"
        />
        <button
          class="px-4 py-2 rounded-lg text-sm font-medium text-white"
          :style="{ backgroundColor: 'var(--accent)', opacity: chatLoading ? 0.5 : 1 }"
          :disabled="chatLoading"
          @click="sendChat"
        >Send</button>
      </div>
    </div>
  </div>
</template>

