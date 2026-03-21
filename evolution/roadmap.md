# ForkCast Roadmap — Future Enhancements

Items noted during development that aren't needed now but worth revisiting.

## Report Pipeline

- **Two-phase plan + execute** — Currently the report agent uses a single tool-use loop where Claude self-directs its research. Upgrade to a two-phase approach: Phase 1 uses `think()` to plan the report outline (sections + data needs), Phase 2 executes a separate tool-use loop per section. Enables section-level retries and more structured output. Noted during Phase 5 design (2026-03-21).

## Chat System

- **Sliding window with summary** — Currently chat uses simple truncation (last N messages). Upgrade to sliding window + LLM-generated summary of earlier messages if users report losing context in long conversations. Noted during Phase 5 design (2026-03-21).

- **Tool call observability** — Report chat executes tool calls during its research loop but doesn't expose which tools were called, what inputs were used, or what results came back. The `tool_calls_json` column in `chat_history` exists but is never written to, and `tool_use` stream events are consumed internally rather than yielded to the caller. Users and developers can't see how the agent reached its conclusions. Fix: yield tool_use events during chat, persist tool call details to chat_history. Noted during first live test (2026-03-21).

- **Chat history truncation** — `_load_chat_history()` loads ALL messages without a LIMIT clause. The `max_history` parameter from the design spec (default 30) is accepted by the function signatures but never applied. Will exceed context limits in long conversations. Noted during code review (2026-03-21).
