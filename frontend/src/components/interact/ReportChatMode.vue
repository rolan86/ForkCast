<script setup>
import { ref, nextTick } from 'vue'
import ChatMessage from './ChatMessage.vue'
import { chatWithReport } from '@/api/reports.js'
import { FileText } from 'lucide-vue-next'

const props = defineProps({
  reportId: { type: String, default: '' },
})

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
  if (!input.value.trim() || !props.reportId || loading.value) return
  const text = input.value.trim()
  input.value = ''
  loading.value = true

  messages.value.push({ role: 'user', content: text })
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  const assistantIdx = messages.value.length - 1
  scrollToBottom()

  try {
    await chatWithReport(props.reportId, text, (eventType, data) => {
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
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100%' }">
    <!-- Header -->
    <div :style="{
      padding: '16px 20px',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', gap: '10px',
    }">
      <FileText :size="18" :style="{ color: 'var(--accent)' }" />
      <div :style="{ fontFamily: 'var(--font-display)', fontSize: '15px', fontWeight: 700 }">
        Report Chat
      </div>
    </div>

    <!-- No report state -->
    <div
      v-if="!reportId"
      :style="{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '14px',
      }"
    >
      Generate a report first to enable Report Chat
    </div>

    <!-- Messages -->
    <div
      v-else
      ref="messagesContainer"
      :style="{ flex: 1, overflowY: 'auto', padding: '20px' }"
    >
      <div v-if="messages.length === 0" :style="{
        textAlign: 'center', color: 'var(--text-tertiary)',
        fontFamily: 'var(--font-body)', fontSize: '13px', marginTop: '40px',
      }">
        Ask questions about the generated report
      </div>
      <ChatMessage
        v-for="(msg, i) in messages"
        :key="i"
        :role="msg.role"
        :content="msg.content"
        :agent-name="msg.role === 'assistant' ? 'Report Analyst' : ''"
        :streaming="msg.streaming || false"
      />
    </div>

    <!-- Input -->
    <div
      v-if="reportId"
      :style="{
        padding: '12px 20px',
        borderTop: '1px solid var(--border)',
        display: 'flex', gap: '10px',
      }"
    >
      <input
        v-model="input"
        @keydown.enter="sendMessage"
        :disabled="loading"
        placeholder="Ask about the report..."
        :style="{
          flex: 1, padding: '10px 14px',
          border: '1px solid var(--border)', borderRadius: '8px',
          fontFamily: 'var(--font-body)', fontSize: '13px',
          backgroundColor: 'var(--surface)', color: 'var(--text-primary)',
          outline: 'none',
        }"
      />
      <button
        @click="sendMessage"
        :disabled="loading || !input.trim()"
        :style="{
          padding: '10px 20px',
          backgroundColor: 'var(--accent)', color: '#fff',
          border: 'none', borderRadius: '8px',
          fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600,
          cursor: 'pointer',
        }"
      >
        Send
      </button>
    </div>
  </div>
</template>
