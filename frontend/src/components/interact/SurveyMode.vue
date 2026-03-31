<script setup>
import { ref, computed } from 'vue'
import AgentAvatar from '@/components/AgentAvatar.vue'
import { surveyAgents, pollAgents } from '@/api/interact.js'

const props = defineProps({
  simulationId: { type: String, required: true },
  agents: { type: Array, default: () => [] },
  selectedAgentIds: { type: Array, default: () => [] },
})

const subMode = ref('structured') // 'structured' | 'freetext'
const question = ref('')
const loading = ref(false)

// Structured poll state
const optionsText = ref('Yes\nNo\nMaybe')
const pollResults = ref(null)
const expandedAgent = ref(null)

// Free-text survey state
const responses = ref({})
const summaryText = ref('')
const surveyed = ref(false)

const BAR_COLORS = ['var(--success)', 'var(--warning)', 'var(--danger)', 'var(--text-tertiary)']

function agentById(id) {
  return props.agents.find(a => a.agent_id === id)
}

async function runPoll() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  pollResults.value = null

  const options = optionsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (options.length < 2) { loading.value = false; return }

  try {
    const agentIds = props.selectedAgentIds.length > 0 ? props.selectedAgentIds : null
    pollResults.value = await pollAgents(props.simulationId, question.value, options, agentIds)
  } catch (err) {
    console.error('Poll error:', err)
  } finally {
    loading.value = false
  }
}

async function runSurvey() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  surveyed.value = true
  summaryText.value = ''

  const targetIds = props.selectedAgentIds.length > 0
    ? props.selectedAgentIds
    : props.agents.map(a => a.agent_id)

  responses.value = {}
  for (const id of targetIds) {
    responses.value[id] = { text: '', streaming: true, agent: agentById(id) }
  }

  try {
    const agentIds = props.selectedAgentIds.length > 0 ? props.selectedAgentIds : null
    await surveyAgents(props.simulationId, question.value, agentIds, (eventType, data) => {
      if (eventType === 'agent_response' && data.type === 'text_delta') {
        if (responses.value[data.agent_id]) {
          responses.value[data.agent_id].text += data.text
        }
      } else if (eventType === 'agent_done') {
        if (responses.value[data.agent_id]) {
          responses.value[data.agent_id].streaming = false
        }
      } else if (eventType === 'summary') {
        summaryText.value = data.text
      }
    })
  } catch (err) {
    console.error('Survey error:', err)
  } finally {
    loading.value = false
  }
}

function submitQuestion() {
  if (subMode.value === 'structured') runPoll()
  else runSurvey()
}

const totalVotes = computed(() => {
  if (!pollResults.value) return 0
  return pollResults.value.results.length
})
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100%' }">
    <!-- Header with sub-mode toggle -->
    <div :style="{ padding: '16px 20px', borderBottom: '1px solid var(--border)', backgroundColor: 'var(--surface-sunken)' }">
      <div :style="{ display: 'flex', gap: '8px', marginBottom: '12px' }">
        <button
          v-for="mode in [{ id: 'structured', label: 'Structured' }, { id: 'freetext', label: 'Free-text' }]"
          :key="mode.id"
          @click="subMode = mode.id"
          :style="{
            padding: '5px 14px', borderRadius: '12px', border: 'none',
            fontFamily: 'var(--font-mono)', fontSize: '11px',
            fontWeight: subMode === mode.id ? 700 : 500,
            backgroundColor: subMode === mode.id ? 'var(--accent)' : 'var(--surface-raised)',
            color: subMode === mode.id ? '#fff' : 'var(--text-secondary)',
            cursor: 'pointer',
          }"
        >
          {{ mode.label }}
        </button>
      </div>
      <div :style="{ display: 'flex', gap: '10px' }">
        <input
          v-model="question"
          @keydown.enter="submitQuestion"
          :placeholder="subMode === 'structured' ? 'Poll question...' : 'Survey question...'"
          :style="{
            flex: 1, padding: '10px 14px',
            border: '1px solid var(--border)', borderRadius: '8px',
            fontFamily: 'var(--font-body)', fontSize: '13px',
            backgroundColor: 'var(--surface)', color: 'var(--text-primary)', outline: 'none',
          }"
        />
        <button
          @click="submitQuestion"
          :disabled="loading || !question.trim()"
          :style="{
            padding: '10px 20px', backgroundColor: 'var(--accent)', color: '#fff',
            border: 'none', borderRadius: '8px',
            fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
          }"
        >
          {{ subMode === 'structured' ? 'Run Poll' : 'Run Survey' }}
        </button>
      </div>
      <textarea
        v-if="subMode === 'structured'"
        v-model="optionsText"
        placeholder="One option per line..."
        :style="{
          marginTop: '10px', width: '100%', padding: '8px 12px',
          border: '1px solid var(--border)', borderRadius: '6px',
          fontFamily: 'var(--font-body)', fontSize: '12px',
          backgroundColor: 'var(--surface)', color: 'var(--text-primary)',
          outline: 'none', resize: 'vertical', minHeight: '60px',
        }"
      />
    </div>

    <!-- Results area -->
    <div :style="{ flex: 1, overflowY: 'auto', padding: '20px' }">
      <!-- Structured poll results -->
      <template v-if="subMode === 'structured' && pollResults">
        <div v-for="(count, option, idx) in pollResults.summary" :key="option" :style="{ marginBottom: '16px' }">
          <div :style="{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px', fontFamily: 'var(--font-body)' }">
            <span :style="{ fontWeight: 600 }">{{ option }}</span>
            <span :style="{ fontWeight: 700 }">{{ count }} ({{ totalVotes ? Math.round(count / totalVotes * 100) : 0 }}%)</span>
          </div>
          <div :style="{ height: '24px', backgroundColor: 'var(--surface-sunken)', borderRadius: '4px', overflow: 'hidden' }">
            <div :style="{
              width: totalVotes ? `${(count / totalVotes) * 100}%` : '0%',
              height: '100%',
              backgroundColor: BAR_COLORS[idx % BAR_COLORS.length],
              borderRadius: '4px',
              display: 'flex', alignItems: 'center', paddingLeft: '6px', gap: '2px',
              transition: 'width var(--duration-slow) var(--ease-out)',
            }">
              <AgentAvatar
                v-for="r in pollResults.results.filter(r => r.choice === option)"
                :key="r.agent_id"
                :name="agentById(r.agent_id)?.name || ''"
                size="xs"
                :style="{ cursor: 'pointer' }"
                @click="expandedAgent = expandedAgent === r.agent_id ? null : r.agent_id"
              />
            </div>
          </div>
        </div>

        <!-- Expanded reasoning -->
        <div v-if="expandedAgent !== null" :style="{
          marginTop: '16px', padding: '14px',
          backgroundColor: 'var(--surface-sunken)', borderRadius: '8px',
          border: '1px solid var(--border)',
        }">
          <div :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-tertiary)', marginBottom: '8px', fontWeight: 600 }">
            REASONING
          </div>
          <div :style="{ fontFamily: 'var(--font-body)', fontSize: '12px', lineHeight: '1.5' }">
            <strong>{{ agentById(expandedAgent)?.name }}:</strong>
            {{ pollResults.results.find(r => r.agent_id === expandedAgent)?.reasoning }}
          </div>
        </div>
      </template>

      <!-- Free-text survey responses -->
      <template v-if="subMode === 'freetext' && surveyed">
        <div v-for="(resp, agentId) in responses" :key="agentId" :style="{
          padding: '12px', border: '1px solid var(--border)', borderRadius: '8px', marginBottom: '8px',
        }">
          <div :style="{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }">
            <AgentAvatar v-if="resp.agent" :name="resp.agent.name" size="xs" />
            <span :style="{ fontFamily: 'var(--font-display)', fontSize: '12px', fontWeight: 600 }">
              {{ resp.agent?.name }}
            </span>
          </div>
          <div :style="{
            fontFamily: 'var(--font-body)', fontSize: '12px', lineHeight: '1.5',
            color: 'var(--text-primary)', paddingLeft: '30px', whiteSpace: 'pre-wrap',
          }">
            {{ resp.text }}
            <span v-if="resp.streaming" :style="{
              display: 'inline-block', width: '7px', height: '14px',
              backgroundColor: 'var(--accent)', marginLeft: '2px',
              borderRadius: '1px', verticalAlign: 'middle', animation: 'blink 1s infinite',
            }" />
          </div>
        </div>

        <!-- AI Summary -->
        <div v-if="summaryText" :style="{
          marginTop: '12px', padding: '14px',
          backgroundColor: 'var(--interact-summary-bg)',
          borderRadius: '8px',
          border: '1px solid var(--interact-summary-border)',
        }">
          <div :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, color: 'var(--accent)', marginBottom: '6px' }">
            AI SUMMARY
          </div>
          <div :style="{ fontFamily: 'var(--font-body)', fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary)' }">
            {{ summaryText }}
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-if="(subMode === 'structured' && !pollResults) || (subMode === 'freetext' && !surveyed)" :style="{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100%', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '14px',
      }">
        {{ subMode === 'structured' ? 'Create a poll question with options' : 'Ask agents an open-ended question' }}
      </div>
    </div>
  </div>
</template>
