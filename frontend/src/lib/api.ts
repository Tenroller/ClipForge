/**
 * API Client for VideoHelper
 * Works with Next.js cookies-based authentication
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export type JobRecord = {
  id: string;
  workflow: 'moneyprinter' | 'brainrot' | string;
  status: string;
  step?: string;
  current_step?: string;
  // Optional runtime logs returned by the backend for live monitoring
  logs?: Array<{
    timestamp: string;
    level: string;
    source?: string;
    message: string;
  }>;
  params?: unknown;
  result?: unknown;
  error_message?: string;
  createdAt?: number;
  updatedAt?: number;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  request_data?: unknown;
  output_url?: string;
  duration_seconds?: number;
  progress?: number;
};

export interface ManagedVideoRecord {
  id: string;
  job_id: string;
  workflow: string;
  file_path: string;
  created_at: string;
  size_bytes?: number;
  download_url?: string;
  posted?: boolean;
}

export type TempFileStats = {
  directories: Array<{
    path: string;
    file_count: number;
    total_size_mb: number;
    exists?: boolean;
    retention_hours?: number;
    max_size_mb?: number;
    last_cleanup?: string;
    oldest_file_age_hours?: number | null;
    files?: Array<{
      name: string;
      size_mb: number;
      modified: string;
    }>;
  }>;
  total_files: number;
  total_size_mb: number;
};

export type CleanupResult = {
  deleted_files: number;
  freed_space_mb: number;
  directories_cleaned: string[];
  errors: string[];
};

/**
 * Helper function to make API requests
 * Uses credentials: 'include' to send cookies automatically
 */
async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers || {}) as Record<string, string>,
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Important: sends cookies with request
  });

  // If we get a 401, redirect to login
  // Note: middleware should also catch this, but this is a fallback
  if (response.status === 401 && typeof window !== 'undefined') {
    window.location.href = '/login';
  }

  return response;
}

// ============================================================================
// Job Management
// ============================================================================

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  const res = await apiFetch(`${API_BASE}/api/jobs?limit=${limit}`);
  const data = await res.json();
  return Array.isArray(data?.jobs) ? data.jobs : [];
}

export async function getJob(jobId: string): Promise<JobRecord | null> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`);
  if (!res.ok) return null;
  return await res.json();
}

export async function remakeJob(jobId: string): Promise<{
  status: string;
  job_id: string;
  original_job_id: string;
  message: string;
  workflow: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/remake`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to remake job');
  }
  return await res.json();
}

export async function cancelJob(jobId: string): Promise<{ status: string; jobId: string }> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to cancel job');
  }

  return await res.json();
}

// ============================================================================
// Video Management
// ============================================================================

export async function listManagedVideosByJob(
  jobId: string,
  limit = 50
): Promise<ManagedVideoRecord[]> {
  try {
    const res = await apiFetch(
      `${API_BASE}/api/videos/managed?job_id=${encodeURIComponent(jobId)}&limit=${limit}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data?.videos) ? data.videos : [];
  } catch {
    return [];
  }
}

export async function getLatestManagedVideo(jobId: string): Promise<ManagedVideoRecord | null> {
  const videos = await listManagedVideosByJob(jobId, 5);
  if (!videos.length) return null;
  // Sort by created_at desc just in case backend didn't
  videos.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  return videos[0];
}

export function downloadUrl(path: string): string {
  const url = new URL(`${API_BASE}/api/download`);
  url.searchParams.set('path', path);
  return url.toString();
}

// ============================================================================
// Video Generation
// ============================================================================

export async function generateMoneyPrinterVideo(params: unknown): Promise<{
  status: string;
  jobId: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/moneyprinter/generate`, {
    method: 'POST',
    body: JSON.stringify(params as unknown),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to start video generation');
  }

  return await res.json();
}

export async function generateBrainrotVideo(params: unknown): Promise<{
  status: string;
  jobId: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/brainrot/generate`, {
    method: 'POST',
    body: JSON.stringify(params as unknown),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));

    // Handle validation errors (array format)
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      const firstError = error.detail[0];
      throw new Error(firstError.msg || 'Validation error');
    }

    // Handle other errors (string format)
    throw new Error(error.detail || 'Failed to start video generation');
  }

  return await res.json();
}

export async function generatePodcastClips(params: unknown): Promise<{
  status: string;
  jobId: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/podcastclips/generate`, {
    method: 'POST',
    body: JSON.stringify(params as unknown),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to start podcast clips generation');
  }

  return await res.json();
}

// ============================================================================
// YouTube Metadata
// ============================================================================

export type YouTubeMetadata = {
  video_id: string;
  title: string;
  channel: string;
  channel_url: string;
  duration: number | null;
  duration_formatted: string;
  thumbnail_url: string;
  description: string;
  view_count: number | null;
  upload_date: string | null;
  resolution: [number, number] | null;
};

export async function getYouTubeMetadata(url: string): Promise<YouTubeMetadata> {
  const encodedUrl = encodeURIComponent(url);
  const res = await apiFetch(`${API_BASE}/api/youtube/metadata?url=${encodedUrl}`);

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to fetch YouTube metadata');
  }

  return await res.json();
}

// ============================================================================
// Cleanup & Maintenance
// ============================================================================

export async function getTempFilesStats(): Promise<TempFileStats> {
  const res = await apiFetch(`${API_BASE}/api/cleanup/temp-files/stats`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get temp files stats');
  }
  return await res.json();
}

export async function cleanupTempFiles(): Promise<CleanupResult> {
  const res = await apiFetch(`${API_BASE}/api/cleanup/temp-files`, {
    method: 'POST',
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to cleanup temp files');
  }

  return await res.json();
}

// ============================================================================
// Job Lineage & Resume
// ============================================================================

export type LineageRecord = {
  id: string;
  status?: string;
  resume_attempt?: number;
  resumed_from?: string;
  children_count?: number;
};

export type JobLineageResponse = {
  ancestors: LineageRecord[];
  descendants: LineageRecord[];
};

export async function getJobLineage(jobId: string): Promise<JobLineageResponse> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${jobId}/lineage`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get job lineage');
  }
  return await res.json();
}

export async function getResumableJobs(): Promise<JobRecord[]> {
  const res = await apiFetch(`${API_BASE}/api/jobs/resumable`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get resumable jobs');
  }
  const data = await res.json();
  return data.jobs || [];
}

export async function resumeJob(jobId: string): Promise<{ job_id: string }> {
  const res = await apiFetch(`${API_BASE}/api/jobs/${jobId}/resume`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to resume job');
  }
  return await res.json();
}

// ============================================================================
// Configuration & Metadata
// ============================================================================

export async function getAvailableModels(): Promise<string[]> {
  try {
    const res = await apiFetch(`${API_BASE}/api/AIvideos/models`);
    if (!res.ok) return ['gemini-2.0-flash']; // Fallback
    const data = await res.json();
    return Array.isArray(data?.models) ? data.models : ['gemini-2.0-flash'];
  } catch {
    return ['gemini-2.0-flash']; // Fallback
  }
}

export async function getAvailableVoices(): Promise<string[]> {
  try {
    const res = await apiFetch(`${API_BASE}/api/voices`);
    if (!res.ok) return ['af_bella']; // Fallback
    const data = await res.json();
    return Array.isArray(data?.voices) ? data.voices : ['af_bella'];
  } catch {
    return ['af_bella']; // Fallback
  }
}

// ============================================================================
// Generic API Helper
// ============================================================================

/**
 * Generic API helper for custom endpoints
 */
export const api = {
  get: (endpoint: string, options?: RequestInit) =>
    apiFetch(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`, {
      ...options,
      method: 'GET',
    }),

  post: (endpoint: string, body?: unknown, options?: RequestInit) =>
    apiFetch(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body as unknown) : undefined,
    }),

  put: (endpoint: string, body?: unknown, options?: RequestInit) =>
    apiFetch(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body as unknown) : undefined,
    }),

  delete: (endpoint: string, options?: RequestInit) =>
    apiFetch(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`, {
      ...options,
      method: 'DELETE',
    }),

  patch: (endpoint: string, body?: unknown, options?: RequestInit) =>
    apiFetch(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(body as unknown) : undefined,
    }),
};

export { API_BASE };
