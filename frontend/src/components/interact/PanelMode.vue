<script setup>
import { ref, computed, nextTick } from 'vue'
import AgentAvatar from '@/components/AgentAvatar.vue'
import { panelInterview } from '@/api/interact.js'

const props = defineProps({
  simulationId: { type: String, required: true },
  agents: { type: Array, default: () => [] },
  selectedAgentIds: { type: Array, default: () => [] },
})

const question = ref('')
const responses = ref({}) // { agent_id: { text, streaming, agent } }
const loading = ref(false)
const asked = ref(false)

const selectedAgents = computed(() =>
  props.agents.filter(a => props.selectedAgentIds.includes(a.agent_id))
)

async function askPanel() {
  if (!question.value.trim() || props.selectedAgentIds.length === 0 || loading.value) return

  loading.value = true
  asked.value = true

  // Initialize response slots
  responses.value = {}
  for (const id of props.selectedAgentIds) {
    const agent = props.agents.find(a => a.agent_id === id)
    responses.value[id] = { text: '', streaming: true, agent }
  }

  try {
    await panelInterview(
      props.simulationId,
      props.selectedAgentIds,
      question.value,
      (eventType, data) => {
        if (eventType === 'agent_response' && data.type === 'text_delta') {
          if (responses.value[data.agent_id]) {
            responses.value[data.agent_id].text += data.text
          }
        } else if (eventType === 'agent_done') {
          if (responses.value[data.agent_id]) {
            responses.value[data.agent_id].streaming = false
          }
        }
      },
    )
  } catch (err) {
    console.error('Panel error:', err)
  } finally {
    loading.value = false
  }
}

const gridCols = computed(() => {
  const count = props.selectedAgentIds.length
  if (count <= 1) return '1fr'
  if (count <= 2) return '1fr 1fr'
  return '1fr 1fr 1fr'
})
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100%' }">
    <!-- Question bar -->
    <div :style="{
      padding: '16px 20px',
      borderBottom: '1px solid var(--border)',
      display: 'flex', gap: '10px',
    }">
      <input
        v-model="question"
        @keydown.enter="askPanel"
        :disabled="loading"
        placeholder="Ask the panel a question..."
        :style="{
          flex: 1, padding: '10px 14px',
          border: '1px solid var(--border)', borderRadius: '8px',
          fontFamily: 'var(--font-body)', fontSize: '13px',
          backgroundColor: 'var(--surface)', color: 'var(--text-primary)',
          outline: 'none',
        }"
      />
      <button
        @click="askPanel"
        :disabled="loading || !question.trim() || selectedAgentIds.length === 0"
        :style="{
          padding: '10px 20px',
          backgroundColor: 'var(--accent)', color: '#fff',
          border: 'none', borderRadius: '8px',
          fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600,
          cursor: 'pointer',
        }"
      >
        Ask Panel
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-if="!asked"
      :style="{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '14px',
      }"
    >
      Select agents from the roster and type a question
    </div>

    <!-- Response grid -->
    <div
      v-else
      :style="{
        flex: 1, overflowY: 'auto', padding: '20px',
        display: 'grid', gridTemplateColumns: gridCols,
        gap: '16px', alignContent: 'start',
      }"
    >
      <div
        v-for="(resp, agentId) in responses"
        :key="agentId"
        :style="{
          border: '1px solid var(--border)',
          borderRadius: '10px',
          overflow: 'hidden',
          backgroundColor: 'var(--surface-raised)',
        }"
      >
        <!-- Agent header -->
        <div :style="{
          padding: '12px 14px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', gap: '8px',
          backgroundColor: 'var(--surface-sunken)',
        }">
          <AgentAvatar v-if="resp.agent" :name="resp.agent.name" size="sm" />
          <div>
            <div :style="{ fontFamily: 'var(--font-display)', fontSize: '12px', fontWeight: 600 }">
              {{ resp.agent?.name }}
            </div>
            <div :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-tertiary)' }">
              {{ resp.agent?.profession }}
            </div>
          </div>
        </div>
        <!-- Response body -->
        <div :style="{
          padding: '14px',
          fontFamily: 'var(--font-body)', fontSize: '13px',
          lineHeight: '1.6', color: 'var(--text-primary)',
          whiteSpace: 'pre-wrap', minHeight: '60px',
        }">
          {{ resp.text }}
          <span
            v-if="resp.streaming"
            :style="{
              display: 'inline-block', width: '7px', height: '14px',
              backgroundColor: 'var(--accent)', marginLeft: '2px',
              borderRadius: '1px', verticalAlign: 'middle',
              animation: 'blink 1s infinite',
            }"
          />
        </div>
      </div>
    </div>
  </div>
</template>
