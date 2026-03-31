<script setup>
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import AgentAvatar from '@/components/AgentAvatar.vue'
import ChatMessage from '@/components/interact/ChatMessage.vue'
import { chatWithAgent } from '@/api/interact.js'
import { X } from 'lucide-vue-next'

const props = defineProps({
  agent: { type: Object, required: true },
  simulationId: { type: String, required: true },
  projectId: { type: String, required: true },
  anchorRect: { type: Object, default: null },
})

const emit = defineEmits(['close'])
const router = useRouter()

const messages = ref([])
const input = ref('')
const loading = ref(false)
const messagesContainer = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function sendMessage() {
  if (!input.value.trim() || loading.value) return
  const text = input.value.trim()
  input.value = ''
  loading.value = true

  messages.value.push({ role: 'user', content: text })
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  const assistantIdx = messages.value.length - 1
  scrollToBottom()

  try {
    await chatWithAgent(props.simulationId, props.agent.agent_id, text, (eventType, data) => {
      if (eventType === 'text_delta') {
        messages.value[assistantIdx].content += data
        scrollToBottom()
      } else if (eventType === 'done') {
        messages.value[assistantIdx].streaming = false
      }
    })
  } catch (err) {
    messages.value[assistantIdx].content = 'Error: ' + err.message
    messages.value[assistantIdx].streaming = false
  } finally {
    loading.value = false
  }
}

function openFull() {
  emit('close')
  router.push({
    name: 'project-interact',
    params: { id: props.projectId },
    query: { mode: 'interview', agent: props.agent.agent_id },
  })
}
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <div
      @click="emit('close')"
      @keydown.escape.window="emit('close')"
      :style="{
        position: 'fixed', inset: 0, zIndex: 40,
        backgroundColor: 'rgba(0,0,0,0.2)',
        backdropFilter: 'blur(4px)',
      }"
    />

    <!-- Popover -->
    <div :style="{
      position: 'fixed',
      top: anchorRect ? `${anchorRect.top}px` : '50%',
      right: '80px',
      zIndex: 50,
      width: '360px', maxHeight: '380px',
      backgroundColor: 'var(--surface-raised)',
      borderRadius: '12px',
      boxShadow: 'var(--shadow-lg)',
      border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
      animation: 'popover-in var(--duration-normal) var(--ease-spring)',
    }">
      <!-- Header -->
      <div :style="{
        padding: '12px 14px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '10px',
      }">
        <AgentAvatar :name="agent.name" size="sm" />
        <div :style="{ flex: 1 }">
          <div :style="{ fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 700 }">
            {{ agent.name }}
          </div>
          <div :style="{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-tertiary)' }">
            @{{ agent.username }}
          </div>
        </div>
        <button
          @click="openFull"
          :style="{
            padding: '3px 8px',
            backgroundColor: 'var(--surface-sunken)',
            borderRadius: '4px',
            border: 'none',
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
          }"
        >
          Open full ↗
        </button>
        <button
          @click="emit('close')"
          :style="{
            background: 'none', border: 'none',
            cursor: 'pointer', color: 'var(--text-tertiary)',
            display: 'flex', alignItems: 'center',
          }"
        >
          <X :size="16" />
        </button>
      </div>

      <!-- Messages -->
      <div ref="messagesContainer" :style="{ flex: 1, overflowY: 'auto', padding: '10px 14px' }">
        <div v-if="messages.length === 0" :style="{
          textAlign: 'center', padding: '20px 0',
          color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '12px',
        }">
          Quick question for {{ agent.name }}?
        </div>
        <ChatMessage
          v-for="(msg, i) in messages"
          :key="i"
          :role="msg.role"
          :content="msg.content"
          :agent-name="msg.role === 'assistant' ? agent.name : ''"
          :streaming="msg.streaming || false"
        />
      </div>

      <!-- Input -->
      <div :style="{ padding: '8px 10px', borderTop: '1px solid var(--border)', display: 'flex', gap: '8px' }">
        <input
          v-model="input"
          @keydown.enter="sendMessage"
          :disabled="loading"
          placeholder="Quick question..."
          :style="{
            flex: 1, padding: '8px 12px',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            fontFamily: 'var(--font-body)',
            fontSize: '12px',
            backgroundColor: 'var(--surface)',
            color: 'var(--text-primary)',
            outline: 'none',
          }"
        />
        <button
          @click="sendMessage"
          :disabled="loading || !input.trim()"
          :style="{
            padding: '8px 14px',
            backgroundColor: 'var(--accent)',
            color: '#fff', border: 'none',
            borderRadius: '6px',
            fontFamily: 'var(--font-display)',
            fontSize: '12px', fontWeight: 600,
            cursor: 'pointer',
          }"
        >
          Send
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style>
@keyframes popover-in {
  from { opacity: 0; transform: scale(0.95) translateY(4px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
