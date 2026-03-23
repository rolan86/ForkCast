/**
 * Base HTTP client wrapping fetch with consistent error handling.
 */

class ApiError extends Error {
  constructor(status, message, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

async function handleResponse(resp) {
  const body = await resp.json().catch(() => null)
  if (!resp.ok) {
    const message = body?.detail || body?.message || `HTTP ${resp.status}`
    throw new ApiError(resp.status, message, body)
  }
  return body
}

export async function apiGet(url) {
  const resp = await fetch(url)
  return handleResponse(resp)
}

export async function apiPost(url, data) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return handleResponse(resp)
}

export async function apiPostMultipart(url, formData) {
  const resp = await fetch(url, {
    method: 'POST',
    body: formData,
  })
  return handleResponse(resp)
}

export async function apiPatch(url, data) {
  const resp = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return handleResponse(resp)
}

export { ApiError }
