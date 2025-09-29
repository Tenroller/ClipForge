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

// Helper function to make API requests
async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
	const headers = {
		'Content-Type': 'application/json',
		...(options.headers || {})
	}

	const response = await fetch(url, {
		...options,
		headers
	})

	return response
}

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  const res = await apiFetch(`${API_BASE}/api/jobs?limit=${limit}`)
  const data = await res.json()
  return Array.isArray(data?.jobs) ? data.jobs : []
}

export async function getJob(jobId: string): Promise<JobRecord | null> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`)
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
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/remake`, {
    method: 'POST'
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to remake job')
  }
  return await res.json()
}

// Managed video helpers (legacy list-videos endpoints fully removed)

// --- New Managed Video helpers (replacement for legacy list-videos scans) ---
export interface ManagedVideoRecord {
  id: string
  job_id: string
  workflow: string
  file_path: string
  created_at: string
  size_bytes?: number
  download_url?: string
  posted?: boolean
}

export async function listManagedVideosByJob(jobId: string, limit = 50): Promise<ManagedVideoRecord[]> {
  try {
    const res = await apiFetch(`${API_BASE}/api/videos/managed?job_id=${encodeURIComponent(jobId)}&limit=${limit}`)
    if (!res.ok) return []
    const data = await res.json()
    return Array.isArray(data?.videos) ? data.videos : []
  } catch {
    return []
  }
}

// Convenience: get first (latest) managed video for a job
export async function getLatestManagedVideo(jobId: string): Promise<ManagedVideoRecord | null> {
  const videos = await listManagedVideosByJob(jobId, 5)
  if (!videos.length) return null
  // Sort by created_at desc just in case backend didn't
  videos.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return videos[0]
}

export function downloadUrl(path: string): string {
  const url = new URL(`${API_BASE}/api/download`)
  url.searchParams.set('path', path)
  return url.toString()
}

// Video generation functions
export async function generateMoneyPrinterVideo(params: any): Promise<{ status: string; jobId: string }> {
  const res = await apiFetch(`${API_BASE}/api/moneyprinter/generate`, {
    method: 'POST',
    body: JSON.stringify(params)
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to start video generation')
  }

  return await res.json()
}

export async function generateBrainrotVideo(params: any): Promise<{ status: string; jobId: string }> {
  const res = await apiFetch(`${API_BASE}/api/brainrot/generate`, {
    method: 'POST',
    body: JSON.stringify(params)
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    
    // Handle validation errors (array format)
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      const firstError = error.detail[0]
      throw new Error(firstError.msg || 'Validation error')
    }
    
    // Handle other errors (string format)
    throw new Error(error.detail || 'Failed to start video generation')
  }

  return await res.json()
}

export async function cancelJob(jobId: string): Promise<{ status: string; jobId: string }> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST'
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to cancel job')
  }

  return await res.json()
}

// Cleanup and maintenance functions
export type TempFileStats = {
  directories: Array<{
    path: string
    file_count: number
    total_size_mb: number
    exists?: boolean
    retention_hours?: number
    max_size_mb?: number
    last_cleanup?: string
    oldest_file_age_hours?: number | null
    files?: Array<{
      name: string
      size_mb: number
      modified: string
    }>
  }>
  total_files: number
  total_size_mb: number
}

export type CleanupResult = {
  deleted_files: number
  freed_space_mb: number
  directories_cleaned: string[]
  errors: string[]
}

export async function getTempFilesStats(): Promise<TempFileStats> {
  const res = await apiFetch(`${API_BASE}/api/cleanup/temp-files/stats`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to get temp files stats')
  }
  return await res.json()
}

export async function cleanupTempFiles(): Promise<CleanupResult> {
  const res = await apiFetch(`${API_BASE}/api/cleanup/temp-files`, {
    method: 'POST'
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to cleanup temp files')
  }

  return await res.json()
}