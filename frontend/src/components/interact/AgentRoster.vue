<script setup>
import AgentAvatar from '@/components/AgentAvatar.vue'
import { Sparkles } from 'lucide-vue-next'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  selectedIds: { type: Array, default: () => [] },
  multiSelect: { type: Boolean, default: false },
  suggestions: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'deselect', 'suggest'])

function toggleAgent(agentId) {
  if (props.disabled) return
  if (props.selectedIds.includes(agentId)) {
    emit('deselect', agentId)
  } else {
    emit('select', agentId)
  }
}

function isSelected(agentId) {
  return props.selectedIds.includes(agentId)
}

function isSuggested(agentId) {
  return props.suggestions.some(s => s.agent_id === agentId)
}

function suggestionReason(agentId) {
  const s = props.suggestions.find(s => s.agent_id === agentId)
  return s ? s.reason : ''
}
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', gap: '6px' }">
    <div
      v-for="agent in agents"
      :key="agent.agent_id"
      @click="toggleAgent(agent.agent_id)"
      :style="{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '10px 12px',
        borderRadius: '8px',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        backgroundColor: isSelected(agent.agent_id)
          ? 'rgba(99,102,241,0.15)'
          : isSuggested(agent.agent_id)
            ? 'rgba(245,158,11,0.1)'
            : 'transparent',
        border: isSelected(agent.agent_id)
          ? '1px solid var(--accent)'
          : '1px solid transparent',
        transition: 'all var(--duration-fast) ease',
      }"
    >
      <AgentAvatar :name="agent.name" size="sm" />
      <div :style="{ flex: 1, minWidth: 0 }">
        <div :style="{
          fontFamily: 'var(--font-display)',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--interact-sidebar-text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }">
          {{ agent.name }}
        </div>
        <div :style="{
          fontFamily: 'var(--font-mono)',
          fontSize: '10px',
          color: 'var(--text-tertiary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }">
          {{ agent.profession }}
        </div>
        <div
          v-if="isSuggested(agent.agent_id)"
          :style="{
            fontFamily: 'var(--font-body)',
            fontSize: '10px',
            color: 'var(--warning)',
            marginTop: '2px',
          }"
        >
          {{ suggestionReason(agent.agent_id) }}
        </div>
      </div>
      <div
        v-if="multiSelect && isSelected(agent.agent_id)"
        :style="{
          width: '16px', height: '16px',
          borderRadius: '3px',
          backgroundColor: 'var(--accent)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '10px', color: '#fff', fontWeight: 700,
        }"
      >✓</div>
    </div>
    <button
      @click="emit('suggest')"
      :style="{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: '6px',
        marginTop: '8px',
        padding: '8px 12px',
        borderRadius: '8px',
        border: '1px dashed var(--text-tertiary)',
        backgroundColor: 'transparent',
        color: 'var(--warning)',
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'opacity var(--duration-fast) ease',
      }"
    >
      <Sparkles :size="14" />
      Suggest agents
    </button>
  </div>
</template>
