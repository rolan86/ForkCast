import { apiGet, apiPost } from './client.js'
import { connectSSE, SSE_STAGES } from '@/lib/sse.js'

export async function createSimulation(projectId, options = {}) {
  const body = {
    project_id: projectId,
    engine_type: options.engineType || 'oasis',
    platforms: options.platforms || ['twitter', 'reddit'],
  }
  const resp = await apiPost('/api/simulations', body)
  return resp.data
}

export async function getSimulation(id) {
  const resp = await apiGet(`/api/simulations/${id}`)
  return resp.data
}

export async function listSimulations() {
  const resp = await apiGet('/api/simulations')
  return resp.data
}

export async function prepareSim(id) {
  const resp = await apiPost(`/api/simulations/${id}/prepare`)
  return resp.data
}

export async function startSim(id) {
  const resp = await apiPost(`/api/simulations/${id}/start`)
  return resp.data
}

export async function stopSim(id) {
  const resp = await apiPost(`/api/simulations/${id}/stop`)
  return resp.data
}

export async function getActions(id) {
  const resp = await apiGet(`/api/simulations/${id}/actions`)
  return resp.data
}

export function streamPrepare(simId, handlers) {
  return connectSSE(
    `/api/simulations/${simId}/prepare/stream`,
    SSE_STAGES.PREPARE_STAGES,
    handlers,
  )
}

export function streamSimRun(simId, handlers) {
  return connectSSE(
    `/api/simulations/${simId}/run/stream`,
    SSE_STAGES.RUN_STAGES,
    handlers,
  )
}
