# First Live Report + Chat: Tool-Use Agent Researches Its Own Simulation

**Date:** 2026-03-21
**Phase:** Phase 5 (Report Pipeline + Chat) — first end-to-end live test
**Tag:** v0.5.0-phase5
**Simulation:** sim_0c1c7eae30e5 (same Open-Source AI Accountability debate from Phase 4)


## What Happened

We ran the report pipeline, report chat, and agent chat live against the completed Phase 4 simulation (5 agents, 26 rounds, 96 actions on simulated Twitter). All three features worked end-to-end on the first attempt.


## Report Generation

The report agent autonomously conducted **5 rounds of tool-use research** before writing a 16,727-character prediction report. It consumed 93,956 input tokens and produced 5,086 output tokens.

**Tool usage pattern:**
- Round 1: 3 tool calls
- Round 2: 5 tool calls
- Round 3: 4 tool calls
- Round 4: 4 tool calls
- Round 5: 3 tool calls

The agent's research strategy emerged without instruction. It was given a system prompt with report guidelines and a simulation summary (agent count, action counts, platforms), plus 5 tools. It chose when and how to use them.

The generated report included:
- Executive summary with stakeholder analysis
- Per-agent behavioral profiles with quotes from the simulation
- Engagement pattern analysis (the 13:1 comment-to-post ratio)
- Thematic analysis of the accountability vs. openness debate
- Forward-looking predictions grounded in the simulation dynamics

**Notably:** The report independently identified the same emergent themes we documented in the Phase 4 evolution note — the EU AI Act discussion, the accountability architecture debate, @prod_deployments as pragmatic middle ground — without being told these were significant.


## Report Chat

Asked "Which agent was most influential in the simulation and why?", the report agent:
- Made **3 rounds of tool calls** before responding (researching agent activity, top posts, and engagement data)
- Produced a 5,096-character analysis
- Answered that influence was "more nuanced than a single name"

This demonstrated the tool-use loop in chat working correctly — the agent doesn't just answer from the report text in its system prompt, it goes back to the raw data for additional research.


## Agent Chat

Asked @propai_sentinel (the enterprise/proprietary AI defender) whether open-source models would match proprietary ones in enterprise reliability:

> "The honest answer: it's a category error to frame this as *performance parity*. Enterprise reliability isn't a benchmark score — it's a bundle of guarantees. Uptime SLAs with financial penalties. Indemnification clauses. Documented data lineage for regulators."

The agent referenced the EU AI Act's conformity assessments, distinguished between "raw capability" and "accountability infrastructure," and acknowledged open-source capability while defending its position — all consistent with its persona and simulation behavior. The response felt like a continuation of the simulation debate, not a generic answer.

**Context injection worked:** The agent's system prompt included its own posts and comments from the simulation (injected from `simulation_actions`), so it could reference what it had actually said and done.


## Issues Found

### Critical: Path Resolution Was Wrong

The report pipeline, report chat, and agent chat all loaded graph data and ChromaDB from `data_dir / simulation_id` — but graph and chroma are stored under `data_dir / project_id` (they're created during graph building, before any simulation exists). Profiles are correctly stored under the simulation directory.

This was caught during code review but would have **silently degraded** the report — the graph_search and graph_explore tools would have returned empty results, and the report agent would have generated a report based only on simulation action data, without any knowledge graph context. No error would have been raised.

**Fix:** Updated path resolution to use `project_dir` for graph.json and chroma, `sim_dir` for profiles.

### Important: Tool Call Observability Gap

During report chat, we know the agent made 3 tool rounds (visible from `stop_reason: 'tool_use'` in stream events), but we cannot see:
- **Which tools** were called (tool_use events are consumed internally, not yielded to the caller)
- **What inputs** were passed to each tool
- **What results** came back

The `chat_history` table only persists the final text response. The `tool_calls_json` column exists but is never written to.

This means there's no way for a user or developer to understand *how* the chat agent reached its conclusions. For a system that claims to do research, this is a significant transparency gap.

### Important: Chat SSE Was Buffering, Not Streaming

The API chat endpoints were using `list()` to collect all stream events before sending any SSE events. This means the client would see nothing until the entire response (including all tool rounds) completed, then receive everything at once. Fixed to use asyncio.Queue bridge for true token-by-token streaming.

### Minor: API Key Field Name Mismatch

CLI commands used `settings.claude_api_key` but the config field is `anthropic_api_key`. Would have crashed every CLI command. Caught in code review, not by tests — the CLI tests mocked `get_settings()`.


## Design Observations

### The Report Agent's Research Strategy

Without explicit guidance on research order, the agent naturally:
1. Started with broad queries (simulation summary, overall statistics)
2. Narrowed to specific agents and their activity patterns
3. Used graph exploration to understand entity relationships
4. Interviewed key agents for qualitative depth
5. Synthesized everything into a structured report

This mirrors how a human analyst would approach the task. The single tool-use loop design (vs. a two-phase plan+execute) was sufficient — Claude's self-directed research produced a thorough report without needing architectural guardrails on research strategy.

### Agent Memory Creates Continuity

The agent chat's "memory" — injecting the agent's own simulation actions into its system prompt — creates a convincing continuity between the simulation and post-simulation conversation. @propai_sentinel's chat response referenced concepts (conformity assessments, accountability infrastructure) that it had actually discussed during the simulation, not generic knowledge about the topic.

### Silent Degradation Is the Real Risk

The path resolution bug highlights a pattern: tools that return empty results instead of errors will silently degrade output quality. The report agent would have generated a report without graph context, and it would have looked plausible but been shallower. This is harder to catch than a crash.


## Technical Details

- **Model:** Claude Sonnet 4.6 (via Anthropic API, tool_use + streaming)
- **Report generation:** ~60 seconds wall clock, 5 tool rounds, ~94K input tokens
- **Report chat:** ~15 seconds, 3 tool rounds, ~19K input tokens
- **Agent chat:** ~5 seconds, no tools, ~2.6K input tokens
- **Data:** Same simulation from Phase 4 (sim_0c1c7eae30e5, 5 agents, 96 actions)
