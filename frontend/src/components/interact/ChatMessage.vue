<script setup>
import AgentAvatar from '@/components/AgentAvatar.vue'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, default: '' },
  agentName: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
  tint: { type: String, default: '' },
})
</script>

<template>
  <div :style="{
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
    flexDirection: role === 'user' ? 'row-reverse' : 'row',
  }">
    <AgentAvatar
      v-if="role === 'assistant' && agentName"
      :name="agentName"
      size="sm"
    />
    <div :style="{
      maxWidth: '80%',
      padding: '10px 14px',
      borderRadius: role === 'user'
        ? '14px 14px 4px 14px'
        : '4px 14px 14px 14px',
      backgroundColor: role === 'user'
        ? 'var(--interact-bubble-user)'
        : tint === 'pro'
          ? 'var(--interact-pro-surface)'
          : tint === 'con'
            ? 'var(--interact-con-surface)'
            : 'var(--interact-bubble-agent)',
      border: '1px solid var(--border-subtle)',
      fontFamily: 'var(--font-body)',
      fontSize: '13px',
      lineHeight: '1.6',
      color: 'var(--text-primary)',
      whiteSpace: 'pre-wrap',
    }">
      {{ content }}
      <span
        v-if="streaming"
        :style="{
          display: 'inline-block',
          width: '7px',
          height: '14px',
          backgroundColor: 'var(--accent)',
          marginLeft: '2px',
          borderRadius: '1px',
          verticalAlign: 'middle',
          animation: 'blink 1s infinite',
        }"
      />
    </div>
  </div>
</template>

<style>
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
</style>
