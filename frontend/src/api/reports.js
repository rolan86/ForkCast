import { apiGet, apiPost } from './client.js'
import { connectSSE } from '@/lib/sse.js'

const REPORT_STAGES = ['loading', 'thinking', 'tool_use', 'forcing', 'complete', 'result']

export async function listReports(simulationId) {
  const url = simulationId
    ? `/api/reports?simulation_id=${encodeURIComponent(simulationId)}`
    : '/api/reports'
  const resp = await apiGet(url)
  return resp.data
}

export async function getReport(reportId) {
  const resp = await apiGet(`/api/reports/${reportId}`)
  return resp.data
}

export async function generateReport(simulationId, options = {}) {
  const resp = await apiPost('/api/reports/generate', {
    simulation_id: simulationId,
    max_tool_rounds: options.maxToolRounds || 10,
  })
  return resp.data
}

export function streamGenerate(reportId, handlers) {
  return connectSSE(
    `/api/reports/${reportId}/generate/stream`,
    REPORT_STAGES,
    handlers,
  )
}

export function exportReportUrl(reportId) {
  return `/api/reports/${reportId}/export`
}

/**
 * POST-based SSE for report chat. Uses fetch + ReadableStream
 * because EventSource only supports GET.
 */
export async function chatWithReport(reportId, message, onEvent) {
  const resp = await fetch('/api/chat/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId, message }),
  })
  if (!resp.ok) throw new Error(`Chat failed: HTTP ${resp.status}`)

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
