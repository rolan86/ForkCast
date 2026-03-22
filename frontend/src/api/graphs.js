import { apiGet } from './client.js'
import { connectSSE, SSE_STAGES } from '@/lib/sse.js'

export async function getGraph(projectId) {
  const resp = await apiGet(`/api/projects/${projectId}/graph`)
  return resp.data
}

export async function getGraphData(projectId) {
  const resp = await apiGet(`/api/projects/${projectId}/graph/data`)
  return resp.data
}

export function buildGraph(projectId) {
  // Fire the blocking POST without awaiting (it completes when pipeline finishes)
  const postPromise = fetch(`/api/projects/${projectId}/build-graph`, { method: 'POST' })
  return postPromise
}

export function streamGraphBuild(projectId, handlers) {
  return connectSSE(
    `/api/projects/${projectId}/build-graph/stream`,
    SSE_STAGES.GRAPH_STAGES,
    handlers,
  )
}
