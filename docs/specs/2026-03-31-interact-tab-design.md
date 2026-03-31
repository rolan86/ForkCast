# Interact Tab — Design Spec

## Goal

Add a dedicated Interact tab to ForkCast's project view with five interaction modes: Agent Interview, Group Panel, Survey/Poll, Agent-to-Agent Debate, and Report Chat. Provide contextual quick-access via a popover chat from the Simulation tab. Features unlock progressively as the simulation matures.

## Non-Goals

- Accessibility (ARIA, screen reader, keyboard nav) — out of scope for this iteration
- Mobile/responsive layout — desktop-first
- Exporting or sharing conversations
- Conversation search/history browser

## Architecture

### UI Placement

**Hybrid approach:**

1. **Interact tab** — 5th tab in `ProjectLayout.vue` (after Simulations, before Reports). Houses all 5 interaction modes. Left sidebar with mode selector + agent roster; right area is the interaction surface.
2. **Contextual popover** — clicking an agent avatar in the Simulation tab opens a lightweight chat popover. Uses the same backend endpoint and conversation history as Interview mode. "Open full" link navigates to the Interact tab.

### Progressive Unlock

| Simulation State | Available Modes |
|-----------------|-----------------|
| **Prepared** | Interview (persona-only), Panel, Survey, Debate (stance-based) |
| **Completed** | All above, enriched with action memory |
| **Report Generated** | All above + Report Chat |

When a mode is locked, its pill in the sidebar is disabled with a tooltip explaining what's needed (e.g., "Generate a report first").

## Interaction Modes

### 1. Agent Interview (1-on-1 Chat)

**Backend:** Existing `POST /api/chat/agent` — no changes needed.

**UI:** Select an agent from the sidebar roster. Right panel shows a standard chat interface with:
- Agent header: avatar, name, username, profession, stance
- Buttons to view persona details and action count (if simulation is completed)
- Message history (user right-aligned, agent left with avatar)
- Text input with Send button

**Conversation ID:** `agent_chat_{simulation_id}_{agent_id}` (existing format).

### 2. Group Panel Interview

**Backend:** New `POST /api/interact/panel`

Request:
```json
{
  "simulation_id": "sim_xxx",
  "agent_ids": [1, 4, 9],
  "question": "Would you trust AI for year-end tax prep?"
}
```

Implementation: fires `agent_chat` for each selected agent concurrently via `asyncio.gather`. Streams responses as they complete with `agent_id` tags so the frontend can route to the correct card.

SSE events:
```
event: agent_response
data: {"agent_id": 1, "type": "text_delta", "text": "..."}

event: agent_done
data: {"agent_id": 1}

event: complete
data: {}
```

**UI:** Left sidebar shows agent roster with checkmarks for selected panel members. "Suggest agents" button at bottom calls the suggest endpoint. Right panel shows:
- Question bar at top (the question being asked)
- Response cards in a grid (1-3 columns depending on count)
- Each card: agent avatar + name header, response body, streaming indicator
- Follow-up input at bottom — sends to all panel members again

**Conversation ID:** `panel_{simulation_id}_{timestamp}`

### 3. Survey / Poll

Two sub-modes toggled via pills: **Structured** (multiple choice) and **Free-text**.

#### 3a. Structured Poll

**Backend:** New `POST /api/interact/poll`

Request:
```json
{
  "simulation_id": "sim_xxx",
  "question": "Would you adopt AI bookkeeping within 12 months?",
  "options": ["Yes, already using or will adopt", "Maybe, need more evidence", "No, will not adopt", "Not applicable"],
  "agent_ids": null
}

```

`agent_ids: null` means all agents. Implementation: for each agent, calls `client.complete()` with a prompt that presents the question and options, instructs the agent (in character) to pick one option and provide brief reasoning. Parses the structured response.

Response:
```json
{
  "results": [
    {"agent_id": 1, "choice": "Maybe, need more evidence", "reasoning": "..."},
    {"agent_id": 9, "choice": "No, will not adopt", "reasoning": "..."}
  ],
  "summary": {"Yes...": 4, "Maybe...": 3, "No...": 2, "N/A": 2}
}
```

**UI:** Bar chart with agent avatar chips on each bar. "Reasoning" section below — click an agent chip to expand their reasoning.

#### 3b. Free-text Survey

**Backend:** New `POST /api/interact/survey`

Request:
```json
{
  "simulation_id": "sim_xxx",
  "question": "What single feature would make you trust AI bookkeeping?",
  "agent_ids": null
}
```

Implementation: fires `agent_chat` for each agent concurrently. After all responses arrive, calls `client.complete()` with all responses to generate a theme summary.

SSE events: same as panel (per-agent streaming), plus a final `summary` event.

**UI:** Response cards in a compact list. AI-generated summary card at the bottom with synthesized themes.

**Conversation ID:** `survey_{simulation_id}_{timestamp}`

### 4. Agent-to-Agent Debate

**Backend:** New `POST /api/interact/debate`

Request:
```json
{
  "simulation_id": "sim_xxx",
  "agent_id_pro": 8,
  "agent_id_con": 9,
  "topic": "Should small businesses fully automate bookkeeping with AI?",
  "rounds": 5,
  "mode": "autoplay"
}
```

Implementation: alternating `agent_chat` calls. Each agent's system prompt includes the debate topic, their assigned side (pro/con), and the full conversation history so far. For auto-play, the backend loops through all rounds and streams. For moderated mode, it returns after each pair of exchanges and waits for the next request.

For moderated mode, the user can interject via `POST /api/interact/debate/continue`:
```json
{
  "simulation_id": "sim_xxx",
  "debate_id": "debate_xxx",
  "interjection": "Bob, what would change your mind?"
}
```

SSE events:
```
event: round_start
data: {"round": 1, "label": "Opening Statements"}

event: agent_response
data: {"agent_id": 8, "side": "pro", "type": "text_delta", "text": "..."}

event: agent_done
data: {"agent_id": 8, "side": "pro"}

event: agent_response
data: {"agent_id": 9, "side": "con", "type": "text_delta", "text": "..."}

event: round_end
data: {"round": 1}

event: complete
data: {}
```

**UI:** Left sidebar shows the two debaters with PRO/AGAINST labels, mode toggle (moderated/auto-play), round progress bar, and topic. Right panel shows the debate thread:
- Round dividers (centered labels)
- Pro agent messages left-aligned (green tint)
- Con agent messages right-aligned (red tint)
- Streaming cursor on active response
- Bottom bar: Pause button (auto-play) or Send button (moderated) + interjection input

**Conversation ID:** `debate_{simulation_id}_{timestamp}`

### 5. Report Chat

**Backend:** Existing `POST /api/chat/report` — no changes needed.

**UI:** Moves from `ReportTab.vue` into the Interact tab as the 5th mode pill. Same chat interface as Interview mode but with the report agent (tool-equipped). `ReportTab.vue` keeps a "Discuss this report" button that navigates to Interact tab with Report mode pre-selected.

Locked until a report has been generated for the selected simulation.

## Smart Agent Suggestions

**Backend:** New `POST /api/interact/suggest`

Request:
```json
{
  "simulation_id": "sim_xxx",
  "topic": "AI bookkeeping trust"
}
```

Implementation: loads all agent profiles, calls `client.complete()` with a prompt that ranks agents by relevance to the topic based on their persona, profession, stance, and interests. Returns a ranked list.

Response:
```json
{
  "suggestions": [
    {"agent_id": 9, "reason": "Strongest opposition — traditional business owner resistant to AI"},
    {"agent_id": 8, "reason": "Strongest advocate — early adopter with measurable results"},
    {"agent_id": 3, "reason": "Tax compliance expert — key concern area for trust"}
  ]
}
```

**UI:** "Suggest agents" button (Sparkles icon) in sidebar. Shows suggestions as highlighted agent cards with one-line reasons. User clicks to add/remove.

**`agent_ids` convention:** Across all endpoints (panel, poll, survey), `agent_ids: null` means "all agents in the simulation." Panel mode requires explicit agent selection (no null). Poll and survey default to all agents but allow filtering via `agent_ids` array. The suggest endpoint's `topic` is sourced from whatever question the user has typed in the current mode's input field.

## Contextual Popover Chat

**Trigger:** Click agent avatar or name in the Simulation tab's agent roster (prepared or completed state).

**UI:** Floating popover (360px wide, max 380px tall) anchored near the clicked agent card:
- Header: avatar, name, username, "Open full" link, close button
- Chat messages (compact, same as Interview)
- Text input + Send

**Behavior:**
- Background content dims slightly
- Dismiss: click ×, click outside, or press Escape
- "Open full" navigates to `/projects/:id/interact?mode=interview&agent=N`
- Shares `conversation_id` with Interview mode — messages persist across both

## Design System Integration

The Interact tab must use ForkCast's existing design tokens from `main.css`. The brainstorming mockups used placeholder colors for rapid iteration — implementation must map to the real token system.

### Aesthetic Direction

**Research console, not chat app.** The Interact tab is a tool for interrogating simulated personas — it should feel like a research instrument, not a messaging UI. Use the existing data-panel dark treatment for the sidebar, structured card layouts over chat bubbles where possible, and the indigo accent system throughout.

### Typography Mapping

| UI Element | Token | Font |
|-----------|-------|------|
| Mode pills, section labels (MODE, DEBATERS, etc.) | `--font-mono` | JetBrains Mono |
| Agent names, headings, round counters | `--font-display` | Satoshi |
| Chat messages, response body text | `--font-body` | General Sans |

### Color Mapping

All colors must use existing design tokens. No hardcoded hex values.

| Mockup Color | Replace With | Token |
|-------------|-------------|-------|
| `#2196F3` (blue) | Indigo accent | `--accent` |
| `#4CAF50` (green) | Success green | `--success` |
| `#F44336` (red) | Danger red | `--danger` |
| `#FF9800` (orange) | Warning amber | `--warning` |
| `#f0f0f0` (light gray) | Sunken surface | `--surface-sunken` |
| `#eee` (border) | Border token | `--border` |
| White backgrounds | Raised surface | `--surface-raised` |
| Agent avatar colors | Derive from `avatarFromName()` utility (existing) | — |

### New Interact Tokens (add to `main.css`)

```css
/* Interact tab — light mode */
--interact-sidebar-bg: var(--data-bg);
--interact-sidebar-text: #fafafa;
--interact-bubble-user: var(--surface-sunken);
--interact-bubble-agent: var(--accent-surface);
--interact-pro-surface: color-mix(in oklch, var(--success) 8%, var(--surface-raised));
--interact-con-surface: color-mix(in oklch, var(--danger) 8%, var(--surface-raised));
--interact-summary-bg: color-mix(in oklch, var(--accent) 6%, var(--surface-raised));
--interact-summary-border: color-mix(in oklch, var(--accent) 25%, var(--border));
--interact-pill-active: var(--accent);
--interact-pill-glow: var(--shadow-glow);
--interact-round-divider: var(--data-bg);
```

### Motion & Transitions

Use existing motion tokens — no arbitrary durations or easings.

| Interaction | Token | Behavior |
|------------|-------|----------|
| Mode switching | `--duration-normal`, `--ease-out` | Crossfade between mode panels |
| Panel cards appearing | `--duration-slow`, `--ease-spring` | Stagger-reveal as responses stream in |
| Popover open/close | `--duration-normal`, `--ease-spring` | Spring-scale from anchor point |
| Agent roster load | `--duration-fast` | Fade-slide in sequentially |
| Debate round divider | `--duration-slow` | Expand from center outward |
| Streaming cursor | Agent's avatar color | Blink animation on active response |

### Structural Tokens

All panels, cards, and containers use: `--surface-raised` background, `--border` borders, `--shadow-sm`/`--shadow-md`/`--shadow-lg` for elevation. The sidebar uses the dark `--interact-sidebar-bg` treatment with `--interact-sidebar-text` for contrast.

### Icons

Use `lucide-vue-next` throughout (existing dependency). No emoji in the UI. "Suggest agents" button uses the `Sparkles` icon tinted with `--warning`.

### Debate Mode — Signature Visual Treatment

Debate is the most visually distinctive mode. Special treatment:
- Pro/con responses use `--interact-pro-surface` / `--interact-con-surface` tinted backgrounds
- Round counter uses `--font-display` at large weight
- Streaming cursor inherits agent's avatar color
- Round dividers use `--interact-round-divider` dark background with `--font-mono` label

### Popover Enhancement

- Background uses `backdrop-filter: blur(4px)` when popover is open
- Popover shadow uses `--shadow-lg` for floating depth
- Anchor arrow/triangle pointing to the clicked agent card

## Frontend Components

### New Files
- `views/InteractTab.vue` — main tab component, mode router
- `components/interact/InterviewMode.vue` — 1-on-1 chat
- `components/interact/PanelMode.vue` — group interview with card grid
- `components/interact/SurveyMode.vue` — free-text + structured toggle
- `components/interact/DebateMode.vue` — debate thread with round management
- `components/interact/ReportChatMode.vue` — report agent chat (extracted from ReportTab)
- `components/interact/AgentRoster.vue` — shared sidebar agent list with selection
- `components/interact/AgentSuggest.vue` — smart suggestion card
- `components/interact/ChatMessage.vue` — shared message bubble component
- `components/simulation/AgentPopoverChat.vue` — popover chat for Sim tab
- `api/interact.js` — API client for new endpoints

### Modified Files
- `views/ProjectLayout.vue` — add Interact tab
- `views/SimulationTab.vue` — add popover trigger on agent avatars
- `views/ReportTab.vue` — replace inline chat with "Discuss" link to Interact tab
- `router/index.js` — add interact route with query params for mode/agent

## Backend Files

### New Files
- `src/forkcast/api/interact_routes.py` — new blueprint with panel/survey/poll/debate/suggest endpoints
- `src/forkcast/interaction/panel.py` — concurrent multi-agent Q&A
- `src/forkcast/interaction/survey.py` — free-text survey + AI summary
- `src/forkcast/interaction/poll.py` — structured poll with option selection
- `src/forkcast/interaction/debate.py` — alternating agent debate with round management
- `src/forkcast/interaction/suggest.py` — topic-based agent ranking

### Modified Files
- `src/forkcast/api/app.py` — register interact_routes blueprint

### No Schema Changes
All interaction data uses the existing `chat_history` table with mode-specific `conversation_id` patterns:
- Interview: `agent_chat_{sim_id}_{agent_id}`
- Panel: `panel_{sim_id}_{timestamp}`
- Survey: `survey_{sim_id}_{timestamp}`
- Debate: `debate_{sim_id}_{timestamp}`
- Report: `{report_id}` (existing)

## Implementation Phases

**Phase 1 — Foundation + Interview + Popover:**
- InteractTab shell with mode pills and agent roster
- Interview mode (wires to existing endpoint)
- Popover chat in Simulation tab
- Route and navigation changes

**Phase 2 — Panel + Report Chat Migration:**
- Panel endpoint and UI
- Move report chat from ReportTab to Interact tab
- Smart agent suggestions endpoint and UI

**Phase 3 — Survey/Poll:**
- Survey endpoint (free-text) and UI
- Poll endpoint (structured) and UI with bar chart
- AI summary generation

**Phase 4 — Debate:**
- Debate endpoint with auto-play and moderated modes
- Debate UI with round management and interjection
