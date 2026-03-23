import { apiGet } from './client.js'

export async function getCapabilities() {
  const resp = await apiGet('/api/capabilities')
  return resp.data
}
