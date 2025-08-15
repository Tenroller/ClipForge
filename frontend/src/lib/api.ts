export type JobRecord = {
  id: string
  workflow: 'moneyprinter' | 'brainrot' | string
  status: string
  step?: string
  params?: any
  result?: any
  createdAt?: number
  updatedAt?: number
}

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

function authHeaders(): HeadersInit {
  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  const apiKey = localStorage.getItem('apiKey')
  if (apiKey) headers['X-API-Key'] = apiKey
  return headers
}

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`, { headers: authHeaders() })
  if (res.status === 401) throw new Error('unauthorized')
  const data = await res.json()
  return Array.isArray(data?.jobs) ? data.jobs : []
}

export async function getJob(jobId: string): Promise<JobRecord | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`, { headers: authHeaders() })
  if (!res.ok) return null
  return await res.json()
}

export type ListedFile = { path: string; name: string; size: number; mtime: number }

export async function listVideos(dir: string): Promise<ListedFile[]> {
  const res = await fetch(`${API_BASE}/api/list-videos?dir=${encodeURIComponent(dir)}`, { headers: authHeaders() })
  if (!res.ok) return []
  const data = await res.json()
  return Array.isArray(data?.files) ? data.files : []
}

export function downloadUrl(path: string): string {
  return `${API_BASE}/api/download?path=${encodeURIComponent(path)}`
}



