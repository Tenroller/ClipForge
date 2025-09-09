import { downloadUrl } from './api'

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}

export type JobStatus = 'queued' | 'running' | 'done' | 'error' | 'cancelled'

export type JobStep = {
  key: string
  label: string
  done: boolean
  active?: boolean
}

export type ManagedJob = {
  id: string
  workflow: 'moneyprinter' | 'brainrot'
  status: JobStatus
  step?: string
  steps: JobStep[]
  result?: any
  error?: string
  createdAt: number
  progress: number
  previewUrl?: string
  canResume?: boolean
  resumeInfo?: {
    lastCompletedStep: string
    completedSteps: number
    nextStep: string
  }
  started_at?: string
  duration_seconds?: number
}

type JobUpdateListener = (job: ManagedJob) => void

class JobManager {
  private jobs = new Map<string, ManagedJob>()
  private connections = new Map<string, WebSocket>()
  private listeners = new Set<JobUpdateListener>()
  private apiBase: string

  constructor(apiBase: string) {
    this.apiBase = apiBase
    
    // Clean up legacy localStorage entries that might contain outdated job IDs
    this.cleanupLegacyData()
  }

  private cleanupLegacyData() {
    try {
      // Get legacy job data that might still exist
      const legacyKeys = ['creator:lastJob', 'compilations:lastJob']
      const legacyJobIds: string[] = []
      
      legacyKeys.forEach(key => {
        const data = localStorage.getItem(key)
        if (data) {
          try {
            const parsed = JSON.parse(data)
            if (parsed?.jobId && typeof parsed.jobId === 'string') {
              legacyJobIds.push(parsed.jobId)
            }
          } catch {}
        }
      })
      
      // Validate legacy job IDs and remove invalid ones
      if (legacyJobIds.length > 0) {
        devLog(`JobManager: Found ${legacyJobIds.length} legacy job IDs, validating...`)
        legacyJobIds.forEach(async (jobId) => {
          try {
            const exists = await this.validateJobExists(jobId, 2) // Fewer retries for legacy cleanup
            if (!exists) {
              devLog(`JobManager: Cleaning up legacy job ${jobId} (404)`)
              // Clear the specific legacy entries for this job
              legacyKeys.forEach(key => {
                const data = localStorage.getItem(key)
                if (data) {
                  try {
                    const parsed = JSON.parse(data)
                    if (parsed?.jobId === jobId) {
                      localStorage.removeItem(key)
                      devLog(`JobManager: Removed legacy localStorage key: ${key}`)
                    }
                  } catch {}
                }
              })
            }
          } catch (e) {
            console.warn(`JobManager: Failed to validate legacy job ${jobId}:`, e)
          }
        })
      }
    } catch (e) {
      console.error('Failed to cleanup legacy data:', e)
    }
  }

  addJob(
    id: string, 
    workflow: 'moneyprinter' | 'brainrot', 
    payload?: any
  ) {
    devLog(`JobManager: Adding new job ${id} with workflow ${workflow}`, payload);
    const job: ManagedJob = {
      id,
      workflow,
      status: 'queued',
      steps: this.getInitialSteps(workflow, payload),
      createdAt: Date.now(),
      progress: 0,
    }
    
    this.jobs.set(id, job)
    this.connectJobUpdates(id)
    this.notifyListeners(job)
    
    // Save to localStorage for persistence
    this.saveToLocalStorage()
  }

  getJob(id: string): ManagedJob | undefined {
    return this.jobs.get(id)
  }

  getAllJobs(): ManagedJob[] {
    return Array.from(this.jobs.values()).sort((a, b) => b.createdAt - a.createdAt)
  }

  getActiveJobs(): ManagedJob[] {
    return this.getAllJobs().filter(job => 
      !['done', 'error', 'cancelled'].includes(job.status)
    )
  }

  async checkResumable(id: string): Promise<boolean> {
    try {
      const res = await fetch(`${this.apiBase}/api/jobs/${id}/resumable`)
      if (res.ok) {
        const data = await res.json()
        return data.can_resume || false
      }
      return false
    } catch {
      return false
    }
  }

  async resumeJob(id: string): Promise<boolean> {
    try {
      // For now, job resumption isn't fully implemented
      // TODO: Implement proper job resumption in the backend
      console.warn('Job resumption is not yet implemented')
      return false
      
      /*
      const res = await fetch(`${this.apiBase}/api/jobs/${id}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (res.ok) {
        // Add the job to active tracking if resume was successful
        const jobData = await res.json()
        if (jobData.id) {
          this.addJob(jobData.id, jobData.workflow, jobData)
        }
        return true
      }
      return false
      */
    } catch (e) {
      console.error('Failed to resume job:', e)
      return false
    }
  }

  async getResumableJobs(): Promise<ManagedJob[]> {
    try {
      const res = await fetch(`${this.apiBase}/api/jobs/resumable`)
      if (res.ok) {
        const data = await res.json()
        return data.resumable_jobs.map((job: any) => {
          // Calculate completed steps based on workflow and current step
          const steps = this.getInitialSteps(job.workflow)
          const currentStepIndex = steps.findIndex(s => s.key === job.step)
          const completedSteps = Math.max(0, currentStepIndex)
          
          return {
            id: job.id,
            workflow: job.workflow,
            status: job.status,
            steps: steps,
            createdAt: new Date(job.created_at).getTime(),
            progress: completedSteps > 0 ? Math.round((completedSteps / steps.length) * 100) : 0,
            error: job.error,
            canResume: true,
            resumeInfo: {
              lastCompletedStep: job.step || 'init',
              completedSteps: completedSteps,
              nextStep: job.next_step || 'unknown'
            }
          }
        })
      }
      return []
    } catch (e) {
      console.error('Failed to get resumable jobs:', e)
      return []
    }
  }

  hasActiveJobs(): boolean {
    return this.getActiveJobs().length > 0
  }

  async checkAndUpdateResumability(): Promise<void> {
    // Check resumability for error/cancelled jobs
    const errorJobs = this.getAllJobs().filter(job => 
      ['error', 'cancelled'].includes(job.status)
    )
    
    for (const job of errorJobs) {
      const canResume = await this.checkResumable(job.id)
      if (canResume !== job.canResume) {
        job.canResume = canResume
        this.jobs.set(job.id, job)
        this.notifyListeners(job)
      }
    }
  }

  removeJob(id: string) {
    this.disconnectJob(id)
    this.jobs.delete(id)
    this.saveToLocalStorage()
  }

  clearCompletedJobs() {
    const toRemove = Array.from(this.jobs.entries())
      .filter(([_, job]) => ['done', 'error', 'cancelled'].includes(job.status))
      .map(([id]) => id)
    
    toRemove.forEach(id => this.removeJob(id))
  }

  addListener(listener: JobUpdateListener) {
    this.listeners.add(listener)
    devLog(`JobManager: Added listener, total listeners: ${this.listeners.size}`)
  }

  removeListener(listener: JobUpdateListener) {
    this.listeners.delete(listener)
    devLog(`JobManager: Removed listener, total listeners: ${this.listeners.size}`)
  }

  private notifyListeners(job: ManagedJob) {
    devLog(`JobManager: Notifying ${this.listeners.size} listeners about job ${job.id}`, job);
    this.listeners.forEach(listener => listener(job))
  }

  private connectJobUpdates(id: string) {
    this.disconnectJob(id)
    
    // First check if the job exists via HTTP before establishing WebSocket
    this.validateJobExists(id).then(exists => {
      if (!exists) {
        devLog(`JobManager: Job ${id} doesn't exist, removing from storage`)
        this.removeJob(id)
        return
      }
      
      // Job exists, proceed with WebSocket connection
      this.establishWebSocketConnection(id)
    }).catch(() => {
      // If validation fails, fall back to polling which will handle 404s
      this.startPollingFallback(id)
    })
  }
  
  private async validateJobExists(id: string, maxRetries: number = 3): Promise<boolean> {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const res = await fetch(`${this.apiBase}/api/jobs/${id}`)
        if (res.status === 404) {
          // If this is the last attempt, consider job doesn't exist
          if (attempt === maxRetries - 1) {
            return false
          }
          // Wait a bit before retrying in case of temporary persistence delay
          await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1)))
          continue
        }
        return res.ok
      } catch (error) {
        // Network error - if this is the last attempt, assume job might exist
        if (attempt === maxRetries - 1) {
          devLog(`JobManager: Network error validating job ${id}, assuming it might exist`)
          return true
        }
        // Wait before retrying
        await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1)))
      }
    }
    // Fallback - assume job might exist if we can't determine
    return true
  }
  
  private establishWebSocketConnection(id: string) {
    const wsUrl = `${this.apiBase.replace('http', 'ws')}/ws/jobs/${id}`
    
    try {
      const ws = new WebSocket(wsUrl)
      this.connections.set(id, ws)
      
      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data)
          await this.updateJob(id, data)
        } catch (e) {
          console.error('Failed to parse job update:', e)
        }
        
        try {
          ws.send('ack')
        } catch {}
      }
      
      ws.onopen = () => {
        try {
          ws.send('hello')
        } catch {}
      }
      
      ws.onerror = (error) => {
        devLog(`WebSocket error for job ${id}:`, error)
        this.startPollingFallback(id)
      }
      
      ws.onclose = (event) => {
        // Check if the close was due to 404 or similar error
        if (event.code === 1000 || event.code === 1006) {
          // Normal closure or connection error, check if job still exists
          this.validateJobExists(id).then(exists => {
            if (!exists) {
              devLog(`JobManager: Job ${id} no longer exists after WebSocket close, removing`)
              this.removeJob(id)
              return
            }
            
            // Job exists but connection closed, try polling fallback
            const job = this.jobs.get(id)
            if (job && !['done', 'error', 'cancelled'].includes(job.status)) {
              this.startPollingFallback(id)
            }
          }).catch(() => {
            // If validation fails, still try polling which will handle cleanup
            const job = this.jobs.get(id)
            if (job && !['done', 'error', 'cancelled'].includes(job.status)) {
              this.startPollingFallback(id)
            }
          })
        }
      }
    } catch {
      this.startPollingFallback(id)
    }
  }

  private startPollingFallback(id: string) {
    const poll = async () => {
      try {
        const res = await fetch(`${this.apiBase}/api/jobs/${id}`)
        
        // Handle 404 - job doesn't exist, remove it from storage
        if (res.status === 404) {
          devLog(`JobManager: Job ${id} not found (404), removing from storage`)
          this.removeJob(id)
          return // Stop polling
        }
        
        // Handle other non-200 responses
        if (!res.ok) {
          // For 4xx errors (except 404), likely the job is gone or invalid
          if (res.status >= 400 && res.status < 500) {
            devLog(`JobManager: Job ${id} returned ${res.status}, removing from storage`)
            this.removeJob(id)
            return // Stop polling
          }
          throw new Error(`HTTP ${res.status}: ${res.statusText}`)
        }
        
        const data = await res.json()
        await this.updateJob(id, data)
        
        const job = this.jobs.get(id)
        if (job && ['done', 'error', 'cancelled'].includes(job.status)) {
          return // Stop polling
        }
        
        setTimeout(poll, 2000)
      } catch (e) {
        // Check if this is a fetch error that might indicate 404
        if (e instanceof Error && e.message.includes('404')) {
          devLog(`JobManager: Job ${id} not found, removing from storage`)
          this.removeJob(id)
          return // Stop polling
        }
        
        // For other fetch errors, retry with exponential backoff
        console.error('Polling failed for job', id, e)
        setTimeout(poll, 5000) // Retry with longer delay
      }
    }
    
    setTimeout(poll, 1000)
  }

  private async updateJob(id: string, data: any) {
    const job = this.jobs.get(id)
    if (!job) return

    const updatedJob: ManagedJob = {
      ...job,
      status: data.status || job.status,
      step: data.step || job.step,
      result: data.result || job.result,
      error: data.error || job.error,
      started_at: data.started_at || job.started_at,
      duration_seconds: data.duration_seconds || job.duration_seconds,
    }

    // Update progress and steps
    updatedJob.steps = this.updateSteps(job.steps, updatedJob.step, updatedJob.status)
    updatedJob.progress = this.calculateProgress(updatedJob.steps)

    // Handle preview URL generation for completed jobs
    if (updatedJob.status === 'done' && !updatedJob.previewUrl) {
      updatedJob.previewUrl = await this.generatePreviewUrl(updatedJob)
    }

    this.jobs.set(id, updatedJob)
    this.notifyListeners(updatedJob)
    this.saveToLocalStorage()

    // Disconnect if job is terminal
    if (['done', 'error', 'cancelled'].includes(updatedJob.status)) {
      this.disconnectJob(id)
    }
  }

  private async generatePreviewUrl(job: ManagedJob): Promise<string | undefined> {
    if (!job.result) return undefined

    try {
      if (typeof job.result.output === 'string') {
        return downloadUrl(job.result.output)
      } else if (typeof job.result.output_dir === 'string') {
        const listRes = await fetch(`${this.apiBase}/api/list-videos?dir=${encodeURIComponent(job.result.output_dir)}`)
        const listJson = await listRes.json()
        const files: Array<{ path: string; mtime: number }> = Array.isArray(listJson?.files) ? listJson.files : []
        files.sort((a, b) => b.mtime - a.mtime)
        if (files[0]?.path) {
          return downloadUrl(files[0].path)
        }
      }
    } catch (e) {
      console.error('Failed to generate preview URL:', e)
    }
    
    return undefined
  }

  private disconnectJob(id: string) {
    const ws = this.connections.get(id)
    if (ws) {
      try {
        ws.close()
      } catch {}
      this.connections.delete(id)
    }
  }

  private getInitialSteps(workflow: string, payload?: any): JobStep[] {
    if (workflow === 'moneyprinter') {
      const baseSteps = [
        { key: 'validate_env', label: 'Validate Environment', done: false },
        { key: 'script_generation', label: 'Generate Script', done: false },
        { key: 'search_terms', label: 'Extract Search Terms', done: false },
        { key: 'stock_download', label: 'Download Stock Videos', done: false },
        { key: 'tts', label: 'Text-to-Speech', done: false },
        { key: 'subtitles', label: 'Generate Subtitles', done: false },
        { key: 'compose_video', label: 'Compose Final Video', done: false },
        { key: 'done', label: 'Complete', done: false },
      ]

      // Add music fetch step if needed
      if (payload?.useMusic && payload?.zipUrl) {
        baseSteps.splice(1, 0, { key: 'fetch_music', label: 'Fetch Background Music', done: false })
      }

      return baseSteps
    } else if (workflow === 'brainrot') {
      return [
        { key: 'process_video', label: 'Process Source Video', done: false },
        { key: 'generate_compilations', label: 'Generate Compilations', done: false },
        { key: 'done', label: 'Complete', done: false },
      ]
    }

    return []
  }

  private updateSteps(steps: JobStep[], currentStep?: string, status?: string): JobStep[] {
    const updatedSteps = [...steps]
    const currentIndex = currentStep ? steps.findIndex(s => s.key === currentStep) : -1
    
    updatedSteps.forEach((step, index) => {
      step.done = index < currentIndex || (status === 'done' && step.key === 'done')
      step.active = step.key === currentStep && !['done', 'error', 'cancelled'].includes(status || '')
    })

    return updatedSteps
  }

  private calculateProgress(steps: JobStep[]): number {
    if (steps.length === 0) return 0
    const completedSteps = steps.filter(s => s.done).length
    return Math.round((completedSteps / steps.length) * 100)
  }

  private saveToLocalStorage() {
    try {
      const jobsData = Array.from(this.jobs.entries()).map(([_, job]) => job)
      localStorage.setItem('jobManager:jobs', JSON.stringify(jobsData))
    } catch (e) {
      console.error('Failed to save jobs to localStorage:', e)
    }
  }

  loadFromLocalStorage() {
    try {
      const saved = localStorage.getItem('jobManager:jobs')
      if (!saved) return

      const jobsData = JSON.parse(saved)
      if (!Array.isArray(jobsData)) return

      devLog(`JobManager: Loading ${jobsData.length} jobs from localStorage`)
      
      // First, filter out any jobs that are clearly invalid (malformed IDs, etc.)
      const validJobsData = jobsData.filter((jobData: any) => {
        if (!jobData.id || !jobData.workflow || typeof jobData.id !== 'string') {
          devLog(`JobManager: Removing malformed job data:`, jobData)
          return false
        }
        return true
      })

      // Load valid jobs into memory but don't auto-connect yet
      validJobsData.forEach((jobData: any) => {
        this.jobs.set(jobData.id, jobData)
      })
      
      // Batch validate all jobs first to remove 404s before attempting connections
      this.batchValidateJobs().then((validJobIds) => {
        devLog(`JobManager: ${validJobIds.length} jobs validated, reconnecting to active ones`)
        
        // Only now connect to active jobs that passed validation
        validJobIds.forEach(jobId => {
          const job = this.jobs.get(jobId)
          if (job && !['done', 'error', 'cancelled'].includes(job.status)) {
            devLog(`JobManager: Reconnecting to active job ${jobId}`)
            this.connectJobUpdates(jobId)
          }
        })
        
        // Check resumability for failed/cancelled jobs
        this.checkAndUpdateResumability()
      }).catch(error => {
        devLog(`JobManager: Error during batch validation:`, error)
      })
      
    } catch (e) {
      console.error('Failed to load jobs from localStorage:', e)
    }
  }

  // Method to batch validate jobs without flooding with requests
  private async batchValidateJobs(): Promise<string[]> {
    const allJobs = this.getAllJobs()
    const validJobIds: string[] = []
    const invalidJobIds: string[] = []

    devLog(`JobManager: Batch validating ${allJobs.length} jobs...`)

    // Validate jobs in small batches to avoid overwhelming the server
    const batchSize = 3
    for (let i = 0; i < allJobs.length; i += batchSize) {
      const batch = allJobs.slice(i, i + batchSize)
      const promises = batch.map(async (job) => {
        try {
          const exists = await this.validateJobExists(job.id, 1) // Single retry for batch validation
          return { jobId: job.id, exists }
        } catch (e) {
          devLog(`JobManager: Failed to validate job ${job.id}:`, e)
          return { jobId: job.id, exists: false }
        }
      })

      const results = await Promise.all(promises)
      results.forEach(({ jobId, exists }) => {
        if (exists) {
          validJobIds.push(jobId)
        } else {
          invalidJobIds.push(jobId)
        }
      })

      // Small delay between batches to be gentle on the server
      if (i + batchSize < allJobs.length) {
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }

    // Remove invalid jobs
    invalidJobIds.forEach(jobId => {
      devLog(`JobManager: Removing non-existent job ${jobId}`)
      this.removeJob(jobId)
    })

    if (invalidJobIds.length > 0) {
      devLog(`JobManager: Cleaned up ${invalidJobIds.length} invalid jobs`)
      this.saveToLocalStorage()
    }

    return validJobIds
  }

  // Method to manually clean up non-existent jobs (can be called externally)
  async validateAllJobs(): Promise<number> {
    return await this.batchValidateJobs().then(validJobIds => {
      const allJobIds = Array.from(this.jobs.keys())
      const removedCount = allJobIds.length - validJobIds.length
      return removedCount
    })
  }

  // Force cleanup of localStorage and invalid jobs
  async forceCleanup(): Promise<void> {
    devLog('JobManager: Starting force cleanup...')
    
    // Clear any problematic localStorage entries
    const keysToCheck = [
      'jobManager:jobs',
      'creator:lastJob', 
      'compilations:lastJob'
    ]
    
    keysToCheck.forEach(key => {
      try {
        const data = localStorage.getItem(key)
        if (data) {
          if (key === 'jobManager:jobs') {
            // Validate job manager data
            const parsed = JSON.parse(data)
            if (Array.isArray(parsed)) {
              const validJobs = parsed.filter(job => 
                job.id && 
                typeof job.id === 'string' && 
                job.workflow && 
                ['moneyprinter', 'brainrot'].includes(job.workflow)
              )
              if (validJobs.length !== parsed.length) {
                devLog(`JobManager: Cleaned ${parsed.length - validJobs.length} malformed jobs from localStorage`)
                localStorage.setItem(key, JSON.stringify(validJobs))
              }
            }
          } else {
            // Legacy job references - validate the job ID format
            const parsed = JSON.parse(data)
            if (parsed?.jobId && typeof parsed.jobId === 'string') {
              // If it looks like a UUID, keep it for validation, otherwise remove
              const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
              if (!uuidRegex.test(parsed.jobId)) {
                devLog(`JobManager: Removing invalid legacy job ID format: ${parsed.jobId}`)
                localStorage.removeItem(key)
              }
            }
          }
        }
      } catch (e) {
        devLog(`JobManager: Error cleaning localStorage key ${key}:`, e)
        localStorage.removeItem(key) // Remove corrupted data
      }
    })
    
    // Validate all current jobs
    await this.batchValidateJobs()
    
    devLog('JobManager: Force cleanup completed')
  }

  destroy() {
    // Close all WebSocket connections
    this.connections.forEach((ws) => {
      try {
        ws.close()
      } catch {}
    })
    this.connections.clear()
    this.jobs.clear()
    this.listeners.clear()
  }
}

export default JobManager
