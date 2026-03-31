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

export async function chatWithAgent(simulationId, agentId, message, onEvent) {
  return postSSE('/api/chat/agent', {
    simulation_id: simulationId,
    agent_id: agentId,
    message,
  }, onEvent)
}

export async function panelInterview(simulationId, agentIds, question, onEvent) {
  return postSSE('/api/interact/panel', {
    simulation_id: simulationId,
    agent_ids: agentIds,
    question,
  }, onEvent)
}

export async function surveyAgents(simulationId, question, agentIds, onEvent) {
  return postSSE('/api/interact/survey', {
    simulation_id: simulationId,
    question,
    agent_ids: agentIds,
  }, onEvent)
}

export async function pollAgents(simulationId, question, options, agentIds) {
  const resp = await apiPost('/api/interact/poll', {
    simulation_id: simulationId,
    question,
    options,
    agent_ids: agentIds,
  })
  return resp.data
}

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

export async function suggestAgents(simulationId, topic) {
  const resp = await apiPost('/api/interact/suggest', {
    simulation_id: simulationId,
    topic,
  })
  return resp.data
}

export { chatWithReport } from './reports.js'
