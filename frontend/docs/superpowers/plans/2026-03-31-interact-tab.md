# Interact Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Interact tab with 5 interaction modes (Interview, Panel, Survey/Poll, Debate, Report Chat), contextual popover chat, and smart agent suggestions.

**Architecture:** Hybrid UI — dedicated Interact tab as 5th tab in ProjectLayout + contextual popover chat from Simulation tab. Backend adds a new `interaction/` module with 5 endpoints under `/api/interact/`, all using SSE streaming. Frontend adds 11 new Vue components. No database schema changes — all data uses existing `chat_history` table with mode-specific `conversation_id` patterns.

**Tech Stack:** Python/FastAPI (backend), Vue 3 + Pinia + Tailwind CSS v4 (frontend), SSE streaming via `sse-starlette`, `asyncio.gather` for concurrent agent calls, Lucide icons.

**Spec:** `docs/specs/2026-03-31-interact-tab-design.md`

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `src/forkcast/interaction/__init__.py` | Package init |
| `src/forkcast/interaction/panel.py` | Concurrent multi-agent Q&A — fires `agent_chat` for N agents via `asyncio.gather` |
| `src/forkcast/interaction/survey.py` | Free-text survey — concurrent agent calls + AI summary generation |
| `src/forkcast/interaction/poll.py` | Structured poll — agents pick from options with reasoning |
| `src/forkcast/interaction/debate.py` | Alternating agent debate with round management |
| `src/forkcast/interaction/suggest.py` | Topic-based agent relevance ranking |
| `src/forkcast/api/interact_routes.py` | FastAPI router with `/api/interact/*` endpoints |

### Backend — Modified Files
| File | Change |
|------|--------|
| `src/forkcast/api/app.py` | Register `interact_router` blueprint |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/api/interact.js` | API client for all interact endpoints (POST-SSE pattern) |
| `frontend/src/views/InteractTab.vue` | Main tab — mode selector, agent roster sidebar, mode panel routing |
| `frontend/src/components/interact/ChatMessage.vue` | Shared message bubble (user/agent) |
| `frontend/src/components/interact/AgentRoster.vue` | Sidebar agent list with selection support |
| `frontend/src/components/interact/AgentSuggest.vue` | Smart suggestion card overlay |
| `frontend/src/components/interact/InterviewMode.vue` | 1-on-1 chat with selected agent |
| `frontend/src/components/interact/PanelMode.vue` | Group interview — card grid with streaming |
| `frontend/src/components/interact/SurveyMode.vue` | Free-text + structured poll toggle |
| `frontend/src/components/interact/DebateMode.vue` | Debate thread with round management |
| `frontend/src/components/interact/ReportChatMode.vue` | Report agent chat (extracted from ReportTab) |
| `frontend/src/components/simulation/AgentPopoverChat.vue` | Popover chat for Sim tab |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/views/ProjectLayout.vue` | Add Interact tab (5th tab) |
| `frontend/src/router/index.js` | Add `project-interact` route with query params |
| `frontend/src/views/SimulationTab.vue` | Add popover trigger on agent avatars |
| `frontend/src/views/ReportTab.vue` | Replace inline chat with "Discuss in Interact" link |
| `frontend/src/assets/main.css` | Add `--interact-*` design tokens |

### Test Files
| File | Tests |
|------|-------|
| `tests/test_interaction_panel.py` | Panel concurrent execution, streaming events, conversation persistence |
| `tests/test_interaction_survey.py` | Survey responses + AI summary, poll structured responses |
| `tests/test_interaction_debate.py` | Debate round management, moderated interjection |
| `tests/test_interaction_suggest.py` | Agent ranking by topic relevance |
| `tests/test_api_interact.py` | API endpoint integration tests |

---

## Phase 1 — Foundation + Interview + Popover

### Task 1: Design Tokens

**Files:**
- Modify: `frontend/src/assets/main.css`

- [ ] **Step 1: Add interact design tokens to light mode section**

Add after the `--shadow-glow` line (around line 46) in the `:root` block:

```css
  /* Interact tab */
  --interact-sidebar-bg: var(--data-bg);
  --interact-sidebar-text: #fafafa;
  --interact-bubble-user: var(--surface-sunken);
  --interact-bubble-agent: var(--accent-surface);
  --interact-pro-surface: #f0fdf4;
  --interact-con-surface: #fef2f2;
  --interact-summary-bg: #eef2ff;
  --interact-summary-border: #c7d2fe;
  --interact-pill-active: var(--accent);
  --interact-pill-glow: var(--shadow-glow);
  --interact-round-divider: var(--data-bg);
```

- [ ] **Step 2: Add interact dark mode overrides**

Add in the `.dark` block (after existing dark overrides):

```css
  --interact-sidebar-bg: #09090b;
  --interact-sidebar-text: #fafafa;
  --interact-bubble-user: var(--surface-sunken);
  --interact-bubble-agent: var(--accent-surface);
  --interact-pro-surface: #052e16;
  --interact-con-surface: #450a0a;
  --interact-summary-bg: #1e1b4b;
  --interact-summary-border: #3730a3;
```

- [ ] **Step 3: Verify tokens render**

Run: `cd frontend && npm run dev`
Open browser DevTools on any page → inspect `:root` → confirm `--interact-*` vars are present.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/assets/main.css
git commit -m "feat(interact): add design tokens for interact tab"
```

---

### Task 2: API Client — `interact.js`

**Files:**
- Create: `frontend/src/api/interact.js`

- [ ] **Step 1: Create the API client module**

This mirrors the pattern from `frontend/src/api/reports.js` — POST-based SSE using `fetch` + `ReadableStream`.

```javascript
/**
 * API client for interact endpoints.
 * All chat-style endpoints use POST-based SSE (fetch + ReadableStream).
 */

import { apiPost } from './client.js'

// ── Shared SSE parser ──────────────────────────────────────────────

async function postSSE(url, body, onEvent) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) throw new Error(`Interact request failed: HTTP ${resp.status}`)

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = null
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ') && currentEvent) {
        try {
          const data = JSON.parse(line.slice(6))
          onEvent(currentEvent, data)
        } catch { /* skip malformed */ }
        currentEvent = null
      }
    }
  }
}

// ── Interview (uses existing endpoint) ─────────────────────────────

export async function chatWithAgent(simulationId, agentId, message, onEvent) {
  return postSSE('/api/chat/agent', {
    simulation_id: simulationId,
    agent_id: agentId,
    message,
  }, onEvent)
}

// ── Panel ──────────────────────────────────────────────────────────

export async function panelInterview(simulationId, agentIds, question, onEvent) {
  return postSSE('/api/interact/panel', {
    simulation_id: simulationId,
    agent_ids: agentIds,
    question,
  }, onEvent)
}

// ── Survey (free-text) ─────────────────────────────────────────────

export async function surveyAgents(simulationId, question, agentIds, onEvent) {
  return postSSE('/api/interact/survey', {
    simulation_id: simulationId,
    question,
    agent_ids: agentIds,
  }, onEvent)
}

// ── Poll (structured) ──────────────────────────────────────────────

export async function pollAgents(simulationId, question, options, agentIds) {
  const resp = await apiPost('/api/interact/poll', {
    simulation_id: simulationId,
    question,
    options,
    agent_ids: agentIds,
  })
  return resp.data
}

// ── Debate ─────────────────────────────────────────────────────────

export async function startDebate(simulationId, agentIdPro, agentIdCon, topic, rounds, mode, onEvent) {
  return postSSE('/api/interact/debate', {
    simulation_id: simulationId,
    agent_id_pro: agentIdPro,
    agent_id_con: agentIdCon,
    topic,
    rounds,
    mode,
  }, onEvent)
}

export async function continueDebate(simulationId, debateId, interjection, onEvent) {
  return postSSE('/api/interact/debate/continue', {
    simulation_id: simulationId,
    debate_id: debateId,
    interjection,
  }, onEvent)
}

// ── Suggest ────────────────────────────────────────────────────────

export async function suggestAgents(simulationId, topic) {
  const resp = await apiPost('/api/interact/suggest', {
    simulation_id: simulationId,
    topic,
  })
  return resp.data
}

// ── Report chat (re-export for convenience) ────────────────────────

export { chatWithReport } from './reports.js'
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/interact.js
git commit -m "feat(interact): add API client for interact endpoints"
```

---

### Task 3: Route + Layout Changes

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/ProjectLayout.vue`

- [ ] **Step 1: Add interact route**

In `frontend/src/router/index.js`, add a new child route inside the `project` route's `children` array, after the reports route:

```javascript
{
  path: 'interact',
  name: 'project-interact',
  component: () => import('@/views/InteractTab.vue'),
},
```

- [ ] **Step 2: Add Interact tab to ProjectLayout**

In `frontend/src/views/ProjectLayout.vue`:

1. Import `MessageSquare` from `lucide-vue-next` (add to existing import)
2. Add to the `tabs` array after Simulations and before Reports:
   ```javascript
   { name: 'project-interact', label: 'Interact', icon: MessageSquare },
   ```

- [ ] **Step 3: Create stub InteractTab.vue**

Create `frontend/src/views/InteractTab.vue` with a minimal placeholder:

```vue
<script setup>
import { ref } from 'vue'

const activeMode = ref('interview')
</script>

<template>
  <div :style="{ display: 'flex', height: '100%', fontFamily: 'var(--font-body)' }">
    <div :style="{
      width: '260px',
      backgroundColor: 'var(--interact-sidebar-bg)',
      color: 'var(--interact-sidebar-text)',
      padding: '16px',
      fontFamily: 'var(--font-mono)',
      fontSize: '12px',
    }">
      Interact sidebar placeholder
    </div>
    <div :style="{ flex: 1, padding: '24px' }">
      <p>Interact tab — {{ activeMode }} mode</p>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Verify tab navigation works**

Run: `cd frontend && npm run dev`
Navigate to a project → confirm 5 tabs visible (Overview, Graph, Simulations, Interact, Reports).
Click Interact → confirm placeholder renders with dark sidebar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/ProjectLayout.vue frontend/src/views/InteractTab.vue
git commit -m "feat(interact): add Interact tab route and layout placeholder"
```

---

### Task 4: ChatMessage Component

**Files:**
- Create: `frontend/src/components/interact/ChatMessage.vue`

- [ ] **Step 1: Create the shared message bubble component**

```vue
<script setup>
import AgentAvatar from '@/components/AgentAvatar.vue'

const props = defineProps({
  role: { type: String, required: true }, // 'user' | 'assistant'
  content: { type: String, default: '' },
  agentName: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
  tint: { type: String, default: '' }, // 'pro' | 'con' | '' for default
})
</script>

<template>
  <div :style="{
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
    flexDirection: role === 'user' ? 'row-reverse' : 'row',
  }">
    <!-- Agent avatar (only for assistant messages) -->
    <AgentAvatar
      v-if="role === 'assistant' && agentName"
      :name="agentName"
      size="sm"
    />

    <!-- Message bubble -->
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
      border: `1px solid var(--border-subtle)`,
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
```

- [ ] **Step 2: Commit**

```bash
mkdir -p frontend/src/components/interact
git add frontend/src/components/interact/ChatMessage.vue
git commit -m "feat(interact): add ChatMessage shared component"
```

---

### Task 5: AgentRoster Component

**Files:**
- Create: `frontend/src/components/interact/AgentRoster.vue`

- [ ] **Step 1: Create the agent roster sidebar component**

```vue
<script setup>
import { computed } from 'vue'
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
        transition: `all var(--duration-fast) ease`,
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

    <!-- Suggest agents button -->
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
        transition: `opacity var(--duration-fast) ease`,
      }"
    >
      <Sparkles :size="14" />
      Suggest agents
    </button>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/interact/AgentRoster.vue
git commit -m "feat(interact): add AgentRoster sidebar component"
```

---

### Task 6: InteractTab + InterviewMode

**Files:**
- Modify: `frontend/src/views/InteractTab.vue`
- Create: `frontend/src/components/interact/InterviewMode.vue`

- [ ] **Step 1: Create InterviewMode component**

```vue
<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import ChatMessage from './ChatMessage.vue'
import { chatWithAgent } from '@/api/interact.js'

const props = defineProps({
  simulationId: { type: String, required: true },
  agent: { type: Object, default: null },
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
  if (!input.value.trim() || !props.agent || loading.value) return
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

// Reset messages when agent changes
watch(() => props.agent?.agent_id, () => {
  messages.value = []
})
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100%' }">
    <!-- Agent header -->
    <div
      v-if="agent"
      :style="{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '12px',
      }"
    >
      <div>
        <div :style="{ fontFamily: 'var(--font-display)', fontSize: '15px', fontWeight: 700 }">
          {{ agent.name }}
        </div>
        <div :style="{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-tertiary)' }">
          @{{ agent.username }} · {{ agent.profession }}
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="!agent"
      :style="{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', fontSize: '14px',
      }"
    >
      Select an agent from the roster to start chatting
    </div>

    <!-- Messages -->
    <div
      v-else
      ref="messagesContainer"
      :style="{ flex: 1, overflowY: 'auto', padding: '20px' }"
    >
      <div
        v-if="messages.length === 0"
        :style="{
          textAlign: 'center', color: 'var(--text-tertiary)',
          fontFamily: 'var(--font-body)', fontSize: '13px', marginTop: '40px',
        }"
      >
        Ask {{ agent.name }} a question to begin the interview
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
    <div
      v-if="agent"
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
        :placeholder="`Ask ${agent.name} a question...`"
        :style="{
          flex: 1, padding: '10px 14px',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          fontFamily: 'var(--font-body)',
          fontSize: '13px',
          backgroundColor: 'var(--surface)',
          color: 'var(--text-primary)',
          outline: 'none',
        }"
      />
      <button
        @click="sendMessage"
        :disabled="loading || !input.trim()"
        :style="{
          padding: '10px 20px',
          backgroundColor: loading || !input.trim() ? 'var(--text-tertiary)' : 'var(--accent)',
          color: '#fff',
          border: 'none',
          borderRadius: '8px',
          fontFamily: 'var(--font-display)',
          fontSize: '13px',
          fontWeight: 600,
          cursor: loading ? 'wait' : 'pointer',
        }"
      >
        Send
      </button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Build out InteractTab.vue with mode selector and interview wiring**

Replace the stub `frontend/src/views/InteractTab.vue` with:

```vue
<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import AgentRoster from '@/components/interact/AgentRoster.vue'
import InterviewMode from '@/components/interact/InterviewMode.vue'
import { suggestAgents as fetchSuggestions } from '@/api/interact.js'

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
const agents = computed(() => {
  const sim = store.currentSimulation
  if (!sim?.agents) return []
  return sim.agents
})
const selectedAgent = computed(() => {
  if (selectedAgentIds.value.length === 0) return null
  return agents.value.find(a => a.agent_id === selectedAgentIds.value[0]) || null
})
const currentSimulation = computed(() => store.currentSimulation)
const simulationId = computed(() => currentSimulation.value?.id || '')

// Mode availability based on simulation state
const simState = computed(() => currentSimulation.value?.status || '')
const hasReport = computed(() => {
  // Check if any report exists for this simulation
  return store.currentSimulation?.has_report || false
})

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

// Get topic from the current mode's context (question input, etc.)
const currentTopic = ref('')

async function onSuggest() {
  if (!simulationId.value) return
  try {
    const result = await fetchSuggestions(simulationId.value, currentTopic.value || 'general discussion')
    suggestions.value = result.suggestions || []
  } catch (e) {
    console.error('Suggest failed:', e)
  }
}

// Pre-select agent from query param
onMounted(() => {
  if (route.query.agent) {
    selectedAgentIds.value = [parseInt(route.query.agent)]
  }
})
</script>

<template>
  <div :style="{ display: 'flex', height: '100%' }">

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
              transition: `all var(--duration-fast) ease`,
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

      <!-- Placeholder for modes added in later phases -->
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
```

- [ ] **Step 3: Verify interview mode works**

Run: `cd frontend && npm run dev` (backend must also be running on :5001)
Navigate to a project with a prepared simulation → Interact tab → select an agent → send a message.
Confirm streaming response appears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/InteractTab.vue frontend/src/components/interact/InterviewMode.vue
git commit -m "feat(interact): implement InteractTab shell with interview mode"
```

---

### Task 7: Contextual Popover Chat

**Files:**
- Create: `frontend/src/components/simulation/AgentPopoverChat.vue`
- Modify: `frontend/src/views/SimulationTab.vue`

- [ ] **Step 1: Create AgentPopoverChat component**

```vue
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
  anchorRect: { type: Object, default: null }, // { top, left, right, bottom }
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
    <!-- Backdrop (click or Escape to dismiss) -->
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
```

- [ ] **Step 2: Wire popover trigger into SimulationTab**

In `frontend/src/views/SimulationTab.vue`:

1. Import `AgentPopoverChat`:
   ```javascript
   import AgentPopoverChat from '@/components/simulation/AgentPopoverChat.vue'
   ```

2. Add local state:
   ```javascript
   const popoverAgent = ref(null)
   const popoverAnchor = ref(null)
   ```

3. Add handler:
   ```javascript
   function openPopover(agent, event) {
     popoverAgent.value = agent
     popoverAnchor.value = event.target.getBoundingClientRect()
   }
   function closePopover() {
     popoverAgent.value = null
   }
   ```

4. On each agent avatar in the roster grid, add `@click="openPopover(agent, $event)"` with `cursor: pointer`.

5. After the template's main content div, add:
   ```vue
   <AgentPopoverChat
     v-if="popoverAgent"
     :agent="popoverAgent"
     :simulation-id="currentSimulation.id"
     :project-id="store.currentProject.id"
     :anchor-rect="popoverAnchor"
     @close="closePopover"
   />
   ```

- [ ] **Step 3: Verify popover works**

Navigate to a project with a prepared simulation → Simulations tab → click an agent avatar.
Confirm popover appears with backdrop blur. Send a message. Click "Open full ↗" — should navigate to Interact tab.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/simulation/AgentPopoverChat.vue frontend/src/views/SimulationTab.vue
git commit -m "feat(interact): add contextual popover chat from Simulation tab"
```

---

## Phase 2 — Panel + Report Chat + Suggestions

### Task 8: Backend — Panel Interaction

**Files:**
- Create: `src/forkcast/interaction/__init__.py`
- Create: `src/forkcast/interaction/panel.py`
- Create: `tests/test_interaction_panel.py`

- [ ] **Step 1: Write failing test for panel**

```python
"""Tests for panel interaction — concurrent multi-agent Q&A."""

import json
from unittest.mock import MagicMock, call

from forkcast.db.connection import get_db, init_db
from forkcast.report.models import StreamEvent


def _setup_panel(db_path, data_dir, sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'prepared', '{}')", (sim_id,),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "Curious researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Test",
         "persona": "Skeptical plumber", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestPanelInteraction:
    def test_streams_responses_from_multiple_agents(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_panel(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Test response"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.panel import panel_interview

        events = list(panel_interview(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_ids=[0, 1],
            question="What do you think?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        agent_done_events = [e for e in events if e.type == "agent_done"]
        assert len(agent_done_events) == 2
        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1

    def test_persists_panel_conversation(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_panel(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="Answer"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.panel import panel_interview

        events = list(panel_interview(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_ids=[0],
            question="Test?",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        # Panel stores a panel-prefixed conversation
        with get_db(tmp_db_path) as conn:
            rows = conn.execute(
                "SELECT conversation_id FROM chat_history WHERE conversation_id LIKE 'panel_%'"
            ).fetchall()
            assert len(rows) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interaction_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forkcast.interaction'`

- [ ] **Step 3: Implement panel module**

Create `src/forkcast/interaction/__init__.py` (empty file).

Create `src/forkcast/interaction/panel.py`:

```python
"""Panel interaction — concurrent multi-agent Q&A."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator

from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _load_chat_history,
    _persist_message,
    _build_agent_system_prompt,
)
from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)


def panel_interview(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    agent_ids: list[int],
    question: str,
    client: Any,
    domains_dir: Path,
) -> Iterator[StreamEvent]:
    """Run a panel interview: ask the same question to multiple agents sequentially.

    Yields StreamEvent with types: agent_response, agent_done, complete, error.
    agent_response data includes agent_id for frontend routing.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data=f"No profiles found for simulation {simulation_id}")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"panel_{simulation_id}_{int(time.time())}"

    # Persist the user question once for the panel
    _persist_message(db_path, conversation_id, "user", question)

    for agent_id in agent_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            yield StreamEvent(type="error", data=f"Agent {agent_id} not found")
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)
        messages = [{"role": "user", "content": question}]

        full_response = ""
        try:
            for event in client.stream(messages=messages, system=system):
                if event.type == "text_delta":
                    full_response += event.data
                    yield StreamEvent(
                        type="agent_response",
                        data={"agent_id": agent_id, "type": "text_delta", "text": event.data},
                    )
                elif event.type == "done":
                    yield StreamEvent(type="agent_done", data={"agent_id": agent_id})
        except Exception as exc:
            logger.error("Panel agent %d error: %s", agent_id, exc)
            yield StreamEvent(type="error", data=f"Agent {agent_id} error: {exc}")

        if full_response:
            _persist_message(db_path, conversation_id, "assistant",
                             json.dumps({"agent_id": agent_id, "text": full_response}))

    yield StreamEvent(type="complete", data={})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_interaction_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/interaction/__init__.py src/forkcast/interaction/panel.py tests/test_interaction_panel.py
git commit -m "feat(interact): add panel interaction module with concurrent agent Q&A"
```

---

### Task 9: Backend — Suggest Agents

**Files:**
- Create: `src/forkcast/interaction/suggest.py`
- Create: `tests/test_interaction_suggest.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for smart agent suggestion."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse


def _setup_suggest(db_path, data_dir, sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'prepared', '{}')", (sim_id,),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "AI researcher",
         "persona": "Curious researcher who loves AI", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI", "ML"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Traditional plumber",
         "persona": "Skeptical of technology", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestSuggestAgents:
    def test_returns_ranked_suggestions(self, tmp_db_path, tmp_data_dir):
        _setup_suggest(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.complete.return_value = LLMResponse(
            text=json.dumps({
                "suggestions": [
                    {"agent_id": 0, "reason": "AI expert — most relevant"},
                    {"agent_id": 1, "reason": "Skeptic perspective — useful contrast"},
                ]
            }),
            input_tokens=100,
            output_tokens=50,
        )

        from forkcast.interaction.suggest import suggest_agents

        result = suggest_agents(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            topic="AI trust",
            client=mock_client,
        )

        assert "suggestions" in result
        assert len(result["suggestions"]) == 2
        assert result["suggestions"][0]["agent_id"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interaction_suggest.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement suggest module**

Create `src/forkcast/interaction/suggest.py`:

```python
"""Smart agent suggestions — rank agents by relevance to a topic."""

import json
import logging
from pathlib import Path
from typing import Any

from forkcast.report.agent_chat import _load_profiles

logger = logging.getLogger(__name__)


def suggest_agents(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    topic: str,
    client: Any,
) -> dict:
    """Rank agents by relevance to the given topic.

    Returns {"suggestions": [{"agent_id": int, "reason": str}, ...]}.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        return {"suggestions": []}

    profiles_summary = "\n".join(
        f"- Agent {p.agent_id}: {p.name} — {p.profession}. "
        f"Interests: {', '.join(p.interests)}. Bio: {p.bio}"
        for p in profiles
    )

    system = (
        "You rank simulation agents by relevance to a topic. "
        "Return JSON: {\"suggestions\": [{\"agent_id\": <int>, \"reason\": \"<one line>\"}]}. "
        "Rank most relevant first. Include all agents."
    )
    messages = [
        {"role": "user", "content": f"Topic: {topic}\n\nAgents:\n{profiles_summary}"}
    ]

    try:
        response = client.complete(messages=messages, system=system)
        return json.loads(response.text)
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Suggest agents failed: %s", exc)
        # Fallback: return all agents unranked
        return {
            "suggestions": [
                {"agent_id": p.agent_id, "reason": f"{p.profession} — {p.bio[:50]}"}
                for p in profiles
            ]
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_interaction_suggest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/interaction/suggest.py tests/test_interaction_suggest.py
git commit -m "feat(interact): add smart agent suggestion module"
```

---

### Task 10: Backend — Interact Routes (Panel + Suggest)

**Files:**
- Create: `src/forkcast/api/interact_routes.py`
- Modify: `src/forkcast/api/app.py`
- Create: `tests/test_api_interact.py`

- [ ] **Step 1: Write failing API test**

```python
"""Tests for interact API routes."""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.config import reset_settings
from forkcast.db.connection import init_db, get_db
from forkcast.llm.client import LLMResponse
from forkcast.report.models import StreamEvent


@pytest.fixture
def app(tmp_db_path, tmp_data_dir, tmp_domains_dir):
    os.environ["FORKCAST_DATA_DIR"] = str(tmp_data_dir)
    os.environ["FORKCAST_DB_PATH"] = str(tmp_db_path)
    os.environ["FORKCAST_DOMAINS_DIR"] = str(tmp_domains_dir)
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    reset_settings()
    init_db(tmp_db_path)
    from forkcast.api.app import create_app
    return create_app()


@pytest.fixture
def setup_sim(tmp_db_path, tmp_data_dir):
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES ('sim1', 'p1', 'prepared', '{}')"
        )
    profiles_dir = tmp_data_dir / "sim1" / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "Researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestInteractRoutes:
    @pytest.mark.asyncio
    async def test_suggest_agents(self, app, setup_sim):
        mock_response = LLMResponse(
            text=json.dumps({"suggestions": [{"agent_id": 0, "reason": "Relevant"}]}),
            input_tokens=10, output_tokens=5,
        )
        with patch("forkcast.api.interact_routes.create_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete.return_value = mock_response
            mock_factory.return_value = mock_client

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/interact/suggest", json={
                    "simulation_id": "sim1",
                    "topic": "AI trust",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert len(data["data"]["suggestions"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_interact.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Create interact_routes.py**

```python
"""Interact API routes — panel, survey, poll, debate, suggest endpoints."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.factory import create_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interact", tags=["interact"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PanelRequest(BaseModel):
    simulation_id: str
    agent_ids: list[int]
    question: str


class SuggestRequest(BaseModel):
    simulation_id: str
    topic: str


# ---------------------------------------------------------------------------
# Helper: SSE streaming wrapper for sync iterators
# ---------------------------------------------------------------------------

def _stream_response(iterator_factory):
    """Wrap a sync Iterator[StreamEvent] into an SSE EventSourceResponse."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def _produce():
        def _run():
            for event in iterator_factory():
                loop.call_soon_threadsafe(queue.put_nowait, event)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        await asyncio.to_thread(_run)

    asyncio.create_task(_produce())

    async def _event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {"event": event.type, "data": json.dumps(event.data, default=str)}

    return EventSourceResponse(_event_generator())


# ---------------------------------------------------------------------------
# Panel endpoint
# ---------------------------------------------------------------------------

@router.post("/panel")
async def panel_endpoint(req: PanelRequest):
    """SSE stream of panel interview responses from multiple agents."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )

    from forkcast.interaction.panel import panel_interview

    return _stream_response(lambda: panel_interview(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.agent_ids, req.question, client, settings.domains_dir,
    ))


# ---------------------------------------------------------------------------
# Suggest endpoint
# ---------------------------------------------------------------------------

@router.post("/suggest")
async def suggest_endpoint(req: SuggestRequest):
    """Rank agents by relevance to a topic."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )

    from forkcast.interaction.suggest import suggest_agents

    result = suggest_agents(
        settings.db_path, settings.data_dir,
        req.simulation_id, req.topic, client,
    )
    return success(result)
```

- [ ] **Step 4: Register router in app.py**

In `src/forkcast/api/app.py`, add after the report_router import/registration:

```python
from forkcast.api.interact_routes import router as interact_router
# ...
app.include_router(interact_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_api_interact.py -v`
Expected: PASS

- [ ] **Step 6: Run all tests to verify no regressions**

Run: `pytest --tb=short`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/forkcast/api/interact_routes.py src/forkcast/api/app.py tests/test_api_interact.py
git commit -m "feat(interact): add interact API routes with panel and suggest endpoints"
```

---

### Task 11: Frontend — PanelMode Component

**Files:**
- Create: `frontend/src/components/interact/PanelMode.vue`
- Modify: `frontend/src/views/InteractTab.vue`

- [ ] **Step 1: Create PanelMode component**

```vue
<script setup>
import { ref, nextTick } from 'vue'
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

import { computed } from 'vue'

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
```

- [ ] **Step 2: Wire PanelMode into InteractTab**

In `frontend/src/views/InteractTab.vue`:

1. Import: `import PanelMode from '@/components/interact/PanelMode.vue'`
2. Replace the `v-else` placeholder with a conditional for panel:

```vue
<PanelMode
  v-else-if="activeMode === 'panel'"
  :simulation-id="simulationId"
  :agents="agents"
  :selected-agent-ids="selectedAgentIds"
/>
```

- [ ] **Step 3: Verify panel mode works**

Run frontend + backend. Navigate to Interact tab → switch to Panel mode → select 2-3 agents → ask a question.
Confirm response cards appear with streaming text.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interact/PanelMode.vue frontend/src/views/InteractTab.vue
git commit -m "feat(interact): add Panel mode with concurrent agent response cards"
```

---

### Task 12: Frontend — ReportChatMode + ReportTab Update

**Files:**
- Create: `frontend/src/components/interact/ReportChatMode.vue`
- Modify: `frontend/src/views/ReportTab.vue`
- Modify: `frontend/src/views/InteractTab.vue`

- [ ] **Step 1: Create ReportChatMode component**

Extract chat logic from ReportTab into a standalone component. This mirrors InterviewMode but uses `chatWithReport` instead of `chatWithAgent`.

```vue
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
```

- [ ] **Step 2: Add "Discuss in Interact" link to ReportTab**

In `frontend/src/views/ReportTab.vue`, replace the inline chat UI section with a button that navigates to the Interact tab:

```vue
<button
  @click="$router.push({
    name: 'project-interact',
    params: { id: store.currentProject.id },
    query: { mode: 'report' },
  })"
  :style="{
    padding: '10px 20px',
    backgroundColor: 'var(--accent)',
    color: '#fff', border: 'none', borderRadius: '8px',
    fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600,
    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
  }"
>
  Discuss this report in Interact →
</button>
```

- [ ] **Step 3: Wire ReportChatMode into InteractTab**

In `frontend/src/views/InteractTab.vue`:

1. Import: `import ReportChatMode from '@/components/interact/ReportChatMode.vue'`
2. Add computed for reportId (look up from store)
3. Add conditional rendering:

```vue
<ReportChatMode
  v-else-if="activeMode === 'report'"
  :report-id="currentReportId"
/>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interact/ReportChatMode.vue frontend/src/views/ReportTab.vue frontend/src/views/InteractTab.vue
git commit -m "feat(interact): add Report Chat mode, link from ReportTab"
```

---

## Phase 3 — Survey / Poll

### Task 13: Backend — Survey + Poll Modules

**Files:**
- Create: `src/forkcast/interaction/survey.py`
- Create: `src/forkcast/interaction/poll.py`
- Create: `tests/test_interaction_survey.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for survey and poll interactions."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.report.models import StreamEvent


def _setup_survey(db_path, data_dir, sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'prepared', '{}')", (sim_id,),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "Researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Test",
         "persona": "Plumber", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestSurvey:
    def test_streams_agent_responses_and_summary(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_survey(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        # stream returns per-agent responses
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="My answer"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])
        # complete returns summary
        mock_client.complete.return_value = LLMResponse(
            text="Theme: everyone wants transparency",
            input_tokens=100, output_tokens=50,
        )

        from forkcast.interaction.survey import free_text_survey

        events = list(free_text_survey(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            question="What matters most?",
            agent_ids=None,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        agent_done = [e for e in events if e.type == "agent_done"]
        assert len(agent_done) == 2
        summary = [e for e in events if e.type == "summary"]
        assert len(summary) == 1


class TestPoll:
    def test_returns_structured_results(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_survey(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.complete.side_effect = [
            LLMResponse(
                text=json.dumps({"choice": "Yes", "reasoning": "I love AI"}),
                input_tokens=10, output_tokens=20,
            ),
            LLMResponse(
                text=json.dumps({"choice": "No", "reasoning": "Too risky"}),
                input_tokens=10, output_tokens=20,
            ),
        ]

        from forkcast.interaction.poll import structured_poll

        result = structured_poll(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            question="Adopt AI?",
            options=["Yes", "No", "Maybe"],
            agent_ids=None,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert "results" in result
        assert len(result["results"]) == 2
        assert "summary" in result
        assert result["summary"]["Yes"] == 1
        assert result["summary"]["No"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_interaction_survey.py -v`
Expected: FAIL

- [ ] **Step 3: Implement survey module**

Create `src/forkcast/interaction/survey.py`:

```python
"""Free-text survey — concurrent agent responses + AI summary."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator, Optional

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _build_agent_system_prompt,
    _persist_message,
)
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)


def free_text_survey(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    question: str,
    agent_ids: Optional[list[int]],
    client: Any,
    domains_dir: Path,
) -> Iterator[StreamEvent]:
    """Run a free-text survey: ask all (or selected) agents, then summarize."""
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data="No profiles found")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"survey_{simulation_id}_{int(time.time())}"

    target_ids = agent_ids if agent_ids else [p.agent_id for p in profiles]
    all_responses = {}

    _persist_message(db_path, conversation_id, "user", question)

    for agent_id in target_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)
        messages = [{"role": "user", "content": question}]

        response_text = ""
        try:
            for event in client.stream(messages=messages, system=system):
                if event.type == "text_delta":
                    response_text += event.data
                    yield StreamEvent(
                        type="agent_response",
                        data={"agent_id": agent_id, "type": "text_delta", "text": event.data},
                    )
                elif event.type == "done":
                    yield StreamEvent(type="agent_done", data={"agent_id": agent_id})
        except Exception as exc:
            logger.error("Survey agent %d error: %s", agent_id, exc)

        if response_text:
            all_responses[agent_id] = response_text
            _persist_message(db_path, conversation_id, "assistant",
                             json.dumps({"agent_id": agent_id, "text": response_text}))

    # Generate AI summary
    if all_responses:
        summary_prompt = "Synthesize these survey responses into key themes (2-3 sentences):\n\n"
        for aid, text in all_responses.items():
            name = next((p.name for p in profiles if p.agent_id == aid), f"Agent {aid}")
            summary_prompt += f"**{name}:** {text}\n\n"

        try:
            summary_resp = client.complete(
                messages=[{"role": "user", "content": summary_prompt}],
                system="You are a research analyst summarizing survey responses. Be concise.",
            )
            yield StreamEvent(type="summary", data={"text": summary_resp.text})
        except Exception as exc:
            logger.error("Summary generation error: %s", exc)

    yield StreamEvent(type="complete", data={})
```

- [ ] **Step 4: Implement poll module**

Create `src/forkcast/interaction/poll.py`:

```python
"""Structured poll — agents pick from options with reasoning."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _build_agent_system_prompt,
    _load_agent_actions,
)

logger = logging.getLogger(__name__)


def structured_poll(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    question: str,
    options: list[str],
    agent_ids: Optional[list[int]],
    client: Any,
    domains_dir: Path,
) -> dict:
    """Run a structured poll. Returns results with choices, reasoning, and summary counts."""
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        return {"results": [], "summary": {}}

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    target_ids = agent_ids if agent_ids else [p.agent_id for p in profiles]

    options_str = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    results = []

    for agent_id in target_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)

        poll_prompt = (
            f"Question: {question}\n\nOptions:\n{options_str}\n\n"
            "Pick ONE option and explain briefly. Reply as JSON: "
            '{"choice": "<exact option text>", "reasoning": "<1-2 sentences>"}'
        )

        try:
            response = client.complete(
                messages=[{"role": "user", "content": poll_prompt}],
                system=system,
            )
            parsed = json.loads(response.text)
            results.append({
                "agent_id": agent_id,
                "choice": parsed.get("choice", options[0]),
                "reasoning": parsed.get("reasoning", ""),
            })
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Poll agent %d error: %s", agent_id, exc)
            results.append({
                "agent_id": agent_id,
                "choice": "Error",
                "reasoning": str(exc),
            })

    # Build summary counts
    summary = {}
    for opt in options:
        summary[opt] = sum(1 for r in results if r["choice"] == opt)

    return {"results": results, "summary": summary}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_interaction_survey.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/interaction/survey.py src/forkcast/interaction/poll.py tests/test_interaction_survey.py
git commit -m "feat(interact): add survey (free-text) and poll (structured) modules"
```

---

### Task 14: Backend — Survey/Poll Routes + Frontend SurveyMode

**Files:**
- Modify: `src/forkcast/api/interact_routes.py` — add survey and poll endpoints
- Create: `frontend/src/components/interact/SurveyMode.vue`
- Modify: `frontend/src/views/InteractTab.vue`

- [ ] **Step 1: Add request models and routes to interact_routes.py**

Add these request models:

```python
class SurveyRequest(BaseModel):
    simulation_id: str
    question: str
    agent_ids: Optional[list[int]] = None

class PollRequest(BaseModel):
    simulation_id: str
    question: str
    options: list[str]
    agent_ids: Optional[list[int]] = None
```

Add survey endpoint (SSE streaming):

```python
@router.post("/survey")
async def survey_endpoint(req: SurveyRequest):
    """SSE stream of free-text survey responses + AI summary."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute("SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider, api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url, ollama_model=settings.ollama_model,
    )
    from forkcast.interaction.survey import free_text_survey
    return _stream_response(lambda: free_text_survey(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.question, req.agent_ids, client, settings.domains_dir,
    ))
```

Add poll endpoint (JSON response, not SSE):

```python
@router.post("/poll")
async def poll_endpoint(req: PollRequest):
    """Run structured poll — returns results with choices and summary."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute("SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider, api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url, ollama_model=settings.ollama_model,
    )
    from forkcast.interaction.poll import structured_poll
    result = structured_poll(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.question, req.options, req.agent_ids, client, settings.domains_dir,
    )
    return success(result)
```

- [ ] **Step 2: Create SurveyMode component**

Create `frontend/src/components/interact/SurveyMode.vue`:

```vue
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
const pollResults = ref(null) // { results: [...], summary: {...} }
const expandedAgent = ref(null)

// Free-text survey state
const responses = ref({}) // { agent_id: { text, streaming, agent } }
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
      <!-- Options input for structured mode -->
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
```

- [ ] **Step 3: Wire into InteractTab**

Add `SurveyMode` import and conditional render for `activeMode === 'survey'`.

- [ ] **Step 4: Run all tests**

Run: `pytest --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/api/interact_routes.py frontend/src/components/interact/SurveyMode.vue frontend/src/views/InteractTab.vue
git commit -m "feat(interact): add Survey/Poll mode — structured + free-text"
```

---

## Phase 4 — Debate

### Task 15: Backend — Debate Module

**Files:**
- Create: `src/forkcast/interaction/debate.py`
- Create: `tests/test_interaction_debate.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for debate interaction."""

import json
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.report.models import StreamEvent


def _setup_debate(db_path, data_dir, sim_id="sim1"):
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES (?, 'p1', 'prepared', '{}')", (sim_id,),
        )
    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Pro AI",
         "persona": "AI advocate", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
        {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Anti AI",
         "persona": "AI skeptic", "age": 50, "gender": "male",
         "profession": "Plumber", "interests": ["DIY"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestDebate:
    def test_autoplay_runs_all_rounds(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_debate(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            StreamEvent(type="text_delta", data="My argument"),
            StreamEvent(type="done", data={"input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn"}),
        ])

        from forkcast.interaction.debate import run_debate

        events = list(run_debate(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            agent_id_pro=0,
            agent_id_con=1,
            topic="Should AI replace bookkeepers?",
            rounds=2,
            mode="autoplay",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        ))

        round_starts = [e for e in events if e.type == "round_start"]
        round_ends = [e for e in events if e.type == "round_end"]
        assert len(round_starts) == 2
        assert len(round_ends) == 2

        agent_done = [e for e in events if e.type == "agent_done"]
        assert len(agent_done) == 4  # 2 agents × 2 rounds

        complete = [e for e in events if e.type == "complete"]
        assert len(complete) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interaction_debate.py -v`
Expected: FAIL

- [ ] **Step 3: Implement debate module**

Create `src/forkcast/interaction/debate.py`:

```python
"""Agent-to-agent debate — alternating rounds with optional moderation."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _build_agent_system_prompt,
    _persist_message,
)
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)

ROUND_LABELS = {
    1: "Opening Statements",
    2: "Rebuttals",
    3: "Cross-Examination",
    4: "Final Arguments",
    5: "Closing Statements",
}


def run_debate(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    agent_id_pro: int,
    agent_id_con: int,
    topic: str,
    rounds: int,
    mode: str,  # "autoplay" or "moderated"
    client: Any,
    domains_dir: Path,
    interjection: str = "",
    debate_history: list[dict] | None = None,
    current_round: int = 1,
) -> Iterator[StreamEvent]:
    """Run a debate between two agents.

    For autoplay: runs all rounds and streams events.
    For moderated: runs one round pair and returns.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data="No profiles found")
        return

    pro = next((p for p in profiles if p.agent_id == agent_id_pro), None)
    con = next((p for p in profiles if p.agent_id == agent_id_con), None)
    if not pro or not con:
        yield StreamEvent(type="error", data="Debate agents not found")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"debate_{simulation_id}_{int(time.time())}"
    history = debate_history or []

    pro_actions = _load_agent_actions(db_path, simulation_id, agent_id_pro)
    con_actions = _load_agent_actions(db_path, simulation_id, agent_id_con)
    pro_base_system = _build_agent_system_prompt(pro, pro_actions, domains_dir, domain_name)
    con_base_system = _build_agent_system_prompt(con, con_actions, domains_dir, domain_name)

    def _debate_system(base_system: str, side: str) -> str:
        return (
            f"{base_system}\n\n"
            f"## Debate Context\n"
            f"Topic: {topic}\n"
            f"Your position: {side.upper()}\n"
            f"Argue passionately from your position. Stay in character.\n"
            f"Keep responses to 2-3 paragraphs."
        )

    pro_system = _debate_system(pro_base_system, "pro")
    con_system = _debate_system(con_base_system, "con")

    start = current_round
    end = rounds + 1 if mode == "autoplay" else current_round + 1

    for round_num in range(start, end):
        label = ROUND_LABELS.get(round_num, f"Round {round_num}")
        yield StreamEvent(type="round_start", data={"round": round_num, "label": label})

        # Pro speaks
        pro_messages = _build_debate_messages(history, "pro", interjection if round_num == start else "")
        pro_text = ""
        for event in client.stream(messages=pro_messages, system=pro_system):
            if event.type == "text_delta":
                pro_text += event.data
                yield StreamEvent(
                    type="agent_response",
                    data={"agent_id": agent_id_pro, "side": "pro", "type": "text_delta", "text": event.data},
                )
            elif event.type == "done":
                yield StreamEvent(type="agent_done", data={"agent_id": agent_id_pro, "side": "pro"})

        history.append({"round": round_num, "side": "pro", "agent_id": agent_id_pro, "text": pro_text})

        # Con speaks
        con_messages = _build_debate_messages(history, "con", "")
        con_text = ""
        for event in client.stream(messages=con_messages, system=con_system):
            if event.type == "text_delta":
                con_text += event.data
                yield StreamEvent(
                    type="agent_response",
                    data={"agent_id": agent_id_con, "side": "con", "type": "text_delta", "text": event.data},
                )
            elif event.type == "done":
                yield StreamEvent(type="agent_done", data={"agent_id": agent_id_con, "side": "con"})

        history.append({"round": round_num, "side": "con", "agent_id": agent_id_con, "text": con_text})

        yield StreamEvent(type="round_end", data={"round": round_num})

        # Persist both responses
        _persist_message(db_path, conversation_id, "assistant",
                         json.dumps({"round": round_num, "pro": pro_text, "con": con_text}))

    yield StreamEvent(type="complete", data={})


def _build_debate_messages(history: list[dict], current_side: str, interjection: str) -> list[dict]:
    """Build message history for a debate participant."""
    messages = []
    for entry in history:
        role = "assistant" if entry["side"] == current_side else "user"
        messages.append({"role": role, "content": entry["text"]})

    if interjection:
        messages.append({"role": "user", "content": f"[Moderator]: {interjection}"})
    elif not messages:
        messages.append({"role": "user", "content": "Please make your opening statement."})
    else:
        messages.append({"role": "user", "content": "Please respond to the previous argument."})

    return messages
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_interaction_debate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/interaction/debate.py tests/test_interaction_debate.py
git commit -m "feat(interact): add debate module with autoplay and moderated modes"
```

---

### Task 16: Backend — Debate Routes

**Files:**
- Modify: `src/forkcast/api/interact_routes.py`

- [ ] **Step 1: Add debate request models and endpoints**

Add request models:

```python
class DebateRequest(BaseModel):
    simulation_id: str
    agent_id_pro: int
    agent_id_con: int
    topic: str
    rounds: int = 5
    mode: str = "autoplay"  # "autoplay" | "moderated"

class DebateContinueRequest(BaseModel):
    simulation_id: str
    debate_id: str
    interjection: str
```

Add debate endpoint:

```python
@router.post("/debate")
async def debate_endpoint(req: DebateRequest):
    """SSE stream of debate rounds between two agents."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute("SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider, api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url, ollama_model=settings.ollama_model,
    )
    from forkcast.interaction.debate import run_debate
    return _stream_response(lambda: run_debate(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.agent_id_pro, req.agent_id_con, req.topic,
        req.rounds, req.mode, client, settings.domains_dir,
    ))
```

Add debate/continue endpoint for moderated mode interjections:

```python
# In-memory debate state for moderated mode (keyed by debate_id)
_debate_state: dict[str, dict] = {}

@router.post("/debate/continue")
async def debate_continue_endpoint(req: DebateContinueRequest):
    """SSE stream of next debate round with moderator interjection."""
    settings = get_settings()

    state = _debate_state.get(req.debate_id)
    if state is None:
        return error(f"Debate not found: {req.debate_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider, api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url, ollama_model=settings.ollama_model,
    )
    from forkcast.interaction.debate import run_debate
    return _stream_response(lambda: run_debate(
        settings.db_path, settings.data_dir, state["simulation_id"],
        state["agent_id_pro"], state["agent_id_con"], state["topic"],
        state["rounds"], "moderated", client, settings.domains_dir,
        interjection=req.interjection,
        debate_history=state["history"],
        current_round=state["current_round"],
    ))
```

Also update the main debate endpoint to store state for moderated mode:

```python
# In the debate_endpoint function, after creating the response:
# For moderated mode, store debate state
if req.mode == "moderated":
    import time
    debate_id = f"debate_{req.simulation_id}_{int(time.time())}"
    _debate_state[debate_id] = {
        "simulation_id": req.simulation_id,
        "agent_id_pro": req.agent_id_pro,
        "agent_id_con": req.agent_id_con,
        "topic": req.topic,
        "rounds": req.rounds,
        "history": [],
        "current_round": 1,
    }
```

- [ ] **Step 2: Run all tests**

Run: `pytest --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/forkcast/api/interact_routes.py
git commit -m "feat(interact): add debate API endpoints with moderated continue support"
```

---

### Task 17: Frontend — DebateMode Component

**Files:**
- Create: `frontend/src/components/interact/DebateMode.vue`
- Modify: `frontend/src/views/InteractTab.vue`

- [ ] **Step 1: Create DebateMode component**

Create `frontend/src/components/interact/DebateMode.vue`:

```vue
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
  if (eventType === 'round_start') {
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
```

- [ ] **Step 2: Wire into InteractTab**

In `frontend/src/views/InteractTab.vue`:
1. Import DebateMode
2. For debate mode, the sidebar should show only two agent slots (pro + con) instead of the full roster
3. Add conditional render: `v-else-if="activeMode === 'debate'"`

- [ ] **Step 3: Verify debate works**

Run frontend + backend → Interact tab → Debate mode → select two agents → enter topic → start debate.
Confirm round dividers, streaming, and alternating messages appear correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interact/DebateMode.vue frontend/src/views/InteractTab.vue
git commit -m "feat(interact): add Debate mode with autoplay and moderated support"
```

---

### Task 18: Final Integration + Smoke Test

**Files:**
- All previously created/modified files

- [ ] **Step 1: Run full backend test suite**

Run: `pytest --tb=short`
Expected: All tests pass (existing + new interaction tests)

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Manual smoke test**

With both servers running:

1. **Interview mode:** Select agent → send message → get streaming response ✓
2. **Panel mode:** Select 3 agents → ask question → see card grid with streaming ✓
3. **Survey mode (free-text):** Ask all agents → see responses + AI summary ✓
4. **Survey mode (structured):** Create poll with options → see bar chart results ✓
5. **Debate mode (autoplay):** Pick 2 agents → set topic → watch rounds play out ✓
6. **Report mode:** Navigate from ReportTab "Discuss" link → chat works ✓
7. **Popover:** Click agent in Simulation tab → popover opens → chat works → "Open full" navigates ✓
8. **Progressive unlock:** With no simulation → modes disabled with tooltip ✓

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(interact): complete Interact tab — all 5 modes + popover + suggestions"
```
