export type JobRecord = {
  id: string
  workflow: 'moneyprinter' | 'brainrot' | string
  status: string
  step?: string
  params?: any
  result?: any
  createdAt?: number
  updatedAt?: number
  request_data?: any  // Added to store original request parameters
}

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

// ...existing code...

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`)
  const data = await res.json()
  return Array.isArray(data?.jobs) ? data.jobs : []
}

export async function getJob(jobId: string): Promise<JobRecord | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`)
  if (!res.ok) return null
  return await res.json()
}

export async function remakeJob(jobId: string): Promise<{
  status: string
  job_id: string
  original_job_id: string
  message: string
  workflow: string
}> {
  const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/remake`, {
    method: 'POST'
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to remake job')
  }
  return await res.json()
}

export type ListedFile = { path: string; name: string; size: number; mtime: number }

export async function listVideos(dir: string): Promise<ListedFile[]> {
  const res = await fetch(`${API_BASE}/api/list-videos?dir=${encodeURIComponent(dir)}`)
  if (!res.ok) return []
  const data = await res.json()
  return Array.isArray(data?.files) ? data.files : []
}

export function downloadUrl(path: string): string {
  return `${API_BASE}/api/download?path=${encodeURIComponent(path)}`
}



