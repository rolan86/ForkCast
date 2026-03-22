import { apiGet, apiPostMultipart } from './client.js'

export async function listProjects() {
  const resp = await apiGet('/api/projects')
  return resp.data
}

export async function getProject(id) {
  const resp = await apiGet(`/api/projects/${id}`)
  return resp.data
}

export async function createProject({ name, domain, requirement, files }) {
  const form = new FormData()
  form.append('name', name)
  form.append('domain', domain)
  form.append('requirement', requirement)
  for (const file of files) {
    form.append('files', file)
  }
  const resp = await apiPostMultipart('/api/projects', form)
  return resp.data
}
