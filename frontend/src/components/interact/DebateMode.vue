<script setup>
import { ref, computed } from 'vue'
import AgentAvatar from '@/components/AgentAvatar.vue'
import ChatMessage from './ChatMessage.vue'
import { startDebate, continueDebate } from '@/api/interact.js'
import { Pause, Play } from 'lucide-vue-next'

const props = defineProps({
  simulationId: { type: String, required: true },
  agents: { type: Array, default: () => [] },
})

const debateState = ref('setup') // 'setup' | 'running' | 'complete'
const topic = ref('')
const proAgentId = ref(null)
const conAgentId = ref(null)
const roundCount = ref(3)
const debateMode = ref('autoplay') // 'autoplay' | 'moderated'
const currentRound = ref(0)
const totalRounds = ref(3)
const messages = ref([]) // { type: 'round'|'message', round?, side?, agentId?, text?, streaming?, label? }
const interjection = ref('')
const loading = ref(false)
const debateId = ref('')

const proAgent = computed(() => props.agents.find(a => a.agent_id === proAgentId.value))
const conAgent = computed(() => props.agents.find(a => a.agent_id === conAgentId.value))
const progressPercent = computed(() => totalRounds.value > 0 ? (currentRound.value / totalRounds.value) * 100 : 0)
const canStart = computed(() => proAgentId.value !== null && conAgentId.value !== null && topic.value.trim())

function selectPro(agentId) { proAgentId.value = agentId }
function selectCon(agentId) { conAgentId.value = agentId }

async function start() {
  if (!canStart.value) return
  debateState.value = 'running'
  totalRounds.value = roundCount.value
  currentRound.value = 0
  messages.value = []
  loading.value = true

  try {
    await startDebate(
      props.simulationId, proAgentId.value, conAgentId.value,
      topic.value, roundCount.value, debateMode.value,
      handleEvent,
    )
  } catch (err) {
    console.error('Debate error:', err)
  } finally {
    loading.value = false
    debateState.value = 'complete'
  }
}

function handleEvent(eventType, data) {
  if (eventType === 'debate_started') {
    debateId.value = data.debate_id
  } else if (eventType === 'round_start') {
    currentRound.value = data.round
    messages.value.push({ type: 'round', round: data.round, label: data.label })
  } else if (eventType === 'agent_response' && data.type === 'text_delta') {
    const last = messages.value[messages.value.length - 1]
    if (last && last.type === 'message' && last.agentId === data.agent_id && last.streaming) {
      last.text += data.text
    } else {
      messages.value.push({
        type: 'message', side: data.side, agentId: data.agent_id,
        text: data.text, streaming: true,
      })
    }
  } else if (eventType === 'agent_done') {
    const last = messages.value.findLast(m => m.type === 'message' && m.agentId === data.agent_id)
    if (last) last.streaming = false
  } else if (eventType === 'round_end') {
    // Round complete
  } else if (eventType === 'complete') {
    debateState.value = 'complete'
  }
}

async function sendInterjection() {
  if (!interjection.value.trim() || loading.value) return
  loading.value = true
  try {
    await continueDebate(props.simulationId, debateId.value, interjection.value, handleEvent)
    interjection.value = ''
  } catch (err) {
    console.error('Interjection error:', err)
  } finally {
    loading.value = false
  }
}

function agentName(agentId) {
  return props.agents.find(a => a.agent_id === agentId)?.name || `Agent ${agentId}`
}
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100%' }">

    <!-- Setup view -->
    <template v-if="debateState === 'setup'">
      <div :style="{ padding: '24px', maxWidth: '600px', margin: '0 auto' }">
        <div :style="{ fontFamily: 'var(--font-display)', fontSize: '18px', fontWeight: 700, marginBottom: '20px' }">
          Set Up Debate
        </div>

        <!-- Topic -->
        <div :style="{ marginBottom: '16px' }">
          <label :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-tertiary)', fontWeight: 600, display: 'block', marginBottom: '6px' }">Topic</label>
          <input v-model="topic" placeholder="Should small businesses automate bookkeeping with AI?"
            :style="{ width: '100%', padding: '10px 14px', border: '1px solid var(--border)', borderRadius: '8px', fontFamily: 'var(--font-body)', fontSize: '13px', backgroundColor: 'var(--surface)', color: 'var(--text-primary)', outline: 'none' }"
          />
        </div>

        <!-- Pro agent -->
        <div :style="{ marginBottom: '12px' }">
          <label :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--success)', fontWeight: 600, display: 'block', marginBottom: '6px' }">PRO Agent</label>
          <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '6px' }">
            <button v-for="agent in agents" :key="'pro-'+agent.agent_id" @click="selectPro(agent.agent_id)"
              :disabled="agent.agent_id === conAgentId"
              :style="{
                padding: '6px 12px', borderRadius: '8px',
                border: proAgentId === agent.agent_id ? '2px solid var(--success)' : '1px solid var(--border)',
                backgroundColor: proAgentId === agent.agent_id ? 'var(--interact-pro-surface)' : 'var(--surface)',
                fontFamily: 'var(--font-body)', fontSize: '12px', cursor: 'pointer',
                opacity: agent.agent_id === conAgentId ? 0.3 : 1,
              }">{{ agent.name }}</button>
          </div>
        </div>

        <!-- Con agent -->
        <div :style="{ marginBottom: '16px' }">
          <label :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--danger)', fontWeight: 600, display: 'block', marginBottom: '6px' }">AGAINST Agent</label>
          <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '6px' }">
            <button v-for="agent in agents" :key="'con-'+agent.agent_id" @click="selectCon(agent.agent_id)"
              :disabled="agent.agent_id === proAgentId"
              :style="{
                padding: '6px 12px', borderRadius: '8px',
                border: conAgentId === agent.agent_id ? '2px solid var(--danger)' : '1px solid var(--border)',
                backgroundColor: conAgentId === agent.agent_id ? 'var(--interact-con-surface)' : 'var(--surface)',
                fontFamily: 'var(--font-body)', fontSize: '12px', cursor: 'pointer',
                opacity: agent.agent_id === proAgentId ? 0.3 : 1,
              }">{{ agent.name }}</button>
          </div>
        </div>

        <!-- Controls -->
        <div :style="{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '20px' }">
          <div>
            <label :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-tertiary)', fontWeight: 600, display: 'block', marginBottom: '6px' }">Rounds</label>
            <select v-model.number="roundCount" :style="{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px', fontFamily: 'var(--font-body)', fontSize: '13px', backgroundColor: 'var(--surface)' }">
              <option :value="3">3 rounds</option>
              <option :value="5">5 rounds</option>
              <option :value="7">7 rounds</option>
            </select>
          </div>
          <div>
            <label :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-tertiary)', fontWeight: 600, display: 'block', marginBottom: '6px' }">Mode</label>
            <div :style="{ display: 'flex', gap: '6px' }">
              <button v-for="m in ['autoplay', 'moderated']" :key="m" @click="debateMode = m"
                :style="{
                  padding: '6px 14px', borderRadius: '12px', border: 'none',
                  fontFamily: 'var(--font-mono)', fontSize: '11px',
                  backgroundColor: debateMode === m ? 'var(--accent)' : 'var(--surface-sunken)',
                  color: debateMode === m ? '#fff' : 'var(--text-secondary)', cursor: 'pointer',
                }">{{ m === 'autoplay' ? 'Auto-play' : 'Moderated' }}</button>
            </div>
          </div>
        </div>

        <button @click="start" :disabled="!canStart"
          :style="{
            padding: '12px 32px', backgroundColor: canStart ? 'var(--accent)' : 'var(--text-tertiary)',
            color: '#fff', border: 'none', borderRadius: '8px',
            fontFamily: 'var(--font-display)', fontSize: '14px', fontWeight: 700, cursor: canStart ? 'pointer' : 'default',
          }">Start Debate</button>
      </div>
    </template>

    <!-- Debate thread -->
    <template v-else>
      <!-- Progress bar -->
      <div :style="{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '12px' }">
        <div :style="{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 800 }">
          {{ currentRound }}/{{ totalRounds }}
        </div>
        <div :style="{ flex: 1, height: '4px', backgroundColor: 'var(--surface-sunken)', borderRadius: '2px', overflow: 'hidden' }">
          <div :style="{ width: progressPercent + '%', height: '100%', backgroundColor: 'var(--accent)', borderRadius: '2px', transition: 'width var(--duration-slow) var(--ease-out)' }" />
        </div>
        <span :style="{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: debateState === 'complete' ? 'var(--success)' : 'var(--warning)' }">
          {{ debateState === 'complete' ? 'COMPLETE' : 'LIVE' }}
        </span>
      </div>

      <!-- Messages -->
      <div :style="{ flex: 1, overflowY: 'auto', padding: '20px' }">
        <template v-for="(msg, i) in messages" :key="i">
          <!-- Round divider -->
          <div v-if="msg.type === 'round'" :style="{ textAlign: 'center', margin: '16px 0' }">
            <span :style="{
              padding: '4px 14px',
              backgroundColor: 'var(--interact-round-divider)',
              borderRadius: '10px',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px', fontWeight: 600,
              color: '#fafafa',
            }">
              ROUND {{ msg.round }} — {{ msg.label }}
            </span>
          </div>

          <!-- Debate message -->
          <ChatMessage
            v-else-if="msg.type === 'message'"
            :role="msg.side === 'pro' ? 'assistant' : 'user'"
            :content="msg.text"
            :agent-name="agentName(msg.agentId)"
            :streaming="msg.streaming || false"
            :tint="msg.side"
          />
        </template>
      </div>

      <!-- Bottom controls -->
      <div :style="{ padding: '14px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: '10px', alignItems: 'center' }">
        <template v-if="debateMode === 'moderated' && debateState !== 'complete'">
          <input v-model="interjection" @keydown.enter="sendInterjection" :disabled="loading"
            placeholder="Interject as moderator..."
            :style="{ flex: 1, padding: '10px 14px', border: '1px solid var(--border)', borderRadius: '8px', fontFamily: 'var(--font-body)', fontSize: '13px', backgroundColor: 'var(--surface)', color: 'var(--text-primary)', outline: 'none' }"
          />
          <button @click="sendInterjection" :disabled="loading || !interjection.trim()"
            :style="{ padding: '10px 20px', backgroundColor: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }">Send</button>
        </template>
        <template v-else-if="debateState === 'complete'">
          <button @click="debateState = 'setup'"
            :style="{ padding: '10px 20px', backgroundColor: 'var(--surface-sunken)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '8px', fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }">
            New Debate
          </button>
        </template>
      </div>
    </template>
  </div>
</template>
