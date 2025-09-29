import { downloadUrl, getLatestManagedVideo } from './api'

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
  isNewlyCreated?: boolean // Flag to track if job was just created
}

type JobUpdateListener = (job: ManagedJob) => void

class JobManager {
  private jobs = new Map<string, ManagedJob>()
  private pollingIntervals = new Map<string, number>()
  private listeners = new Set<JobUpdateListener>()
  private apiBase: string
  private lineageCache = new Map<string, { ancestors: any[]; descendants: any[]; fetchedAt: number }>()

  constructor(apiBase: string) {
    this.apiBase = apiBase
    
    // Load jobs from localStorage on startup
    this.loadFromLocalStorage()
    
    // Start initial polling for any active jobs
    const activeJobs = Array.from(this.jobs.values())
      .filter(job => !['done', 'error', 'cancelled'].includes(job.status))
    
    devLog(`JobManager: Starting polling for ${activeJobs.length} active jobs`)
    activeJobs.forEach(job => this.startPolling(job.id))

    // Auto-cleanup completed jobs after 10 minutes
    setInterval(() => {
      this.cleanupOldJobs()
    }, 10 * 60 * 1000)
  }

  addJob(job: ManagedJob) {
    devLog(`JobManager: Adding job ${job.id}`)
    // Mark as newly created and schedule removal of flag after 5 seconds
    job.isNewlyCreated = true
    this.jobs.set(job.id, job)
    this.saveToLocalStorage()
    this.notifyListeners(job)
    
    // Remove the "newly created" flag after 5 seconds
    setTimeout(() => {
      const existingJob = this.jobs.get(job.id)
      if (existingJob && existingJob.isNewlyCreated) {
        existingJob.isNewlyCreated = false
        this.jobs.set(job.id, existingJob)
        this.saveToLocalStorage()
        this.notifyListeners(existingJob)
      }
    }, 5000)
    
    // Start polling for updates
    this.startPolling(job.id)
  }

  getJob(id: string): ManagedJob | undefined {
    return this.jobs.get(id)
  }

  getAllJobs(): ManagedJob[] {
    return Array.from(this.jobs.values())
  }

  removeJob(id: string) {
    devLog(`JobManager: Removing job ${id}`)
    this.disconnectJob(id)
    this.jobs.delete(id)
    this.saveToLocalStorage()
  }

  // Add listener
  addListener(listener: JobUpdateListener) {
    this.listeners.add(listener)
    devLog(`JobManager: Added listener, total listeners: ${this.listeners.size}`)
  }

  // Remove listener
  removeListener(listener: JobUpdateListener) {
    this.listeners.delete(listener)
    devLog(`JobManager: Removed listener, total listeners: ${this.listeners.size}`)
  }

  // Notify all listeners of job update
  private notifyListeners(job: ManagedJob) {
    devLog(`JobManager: Notifying ${this.listeners.size} listeners about job ${job.id}`, job)
    this.listeners.forEach(listener => listener(job))
  }

  private startPolling(id: string) {
    // Clear any existing polling interval for this job
    this.stopPolling(id)
    
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

        // Stale detection: if job has been queued/running too long, mark as error locally
        const polledJob = this.jobs.get(id)
        if (polledJob && ['queued', 'running'].includes(polledJob.status)) {
          const maxAgeMs = 6 * 60 * 60 * 1000 // 6 hours
          const age = Date.now() - polledJob.createdAt
          if (age > maxAgeMs) {
            polledJob.status = 'error'
            polledJob.error = 'Marked stale: exceeded 6h without completion'
            this.jobs.set(id, polledJob)
            this.notifyListeners(polledJob)
            this.saveToLocalStorage()
            this.stopPolling(id)
            return
          }
        }
        
        const doneCheckJob = this.jobs.get(id)
        if (doneCheckJob && ['done', 'error', 'cancelled'].includes(doneCheckJob.status)) {
          this.stopPolling(id)
          return // Stop polling
        }
        
        // Continue polling if job is still active
        const intervalId = window.setTimeout(poll, 2000)
        this.pollingIntervals.set(id, intervalId)
      } catch (e) {
        // Check if this is a fetch error that might indicate 404
        if (e instanceof Error && e.message.includes('404')) {
          devLog(`JobManager: Job ${id} not found, removing from storage`)
          this.removeJob(id)
          return // Stop polling
        }
        
        // For other fetch errors, retry with exponential backoff
        console.error('Polling failed for job', id, e)
        const intervalId = window.setTimeout(poll, 5000) // Retry with longer delay
        this.pollingIntervals.set(id, intervalId)
      }
    }
    
    // Start polling immediately, then continue with interval
    const intervalId = window.setTimeout(poll, 1000)
    this.pollingIntervals.set(id, intervalId)
  }

  private stopPolling(id: string) {
    const intervalId = this.pollingIntervals.get(id)
    if (intervalId) {
      clearTimeout(intervalId)
      this.pollingIntervals.delete(id)
    }
  }

  private disconnectJob(id: string) {
    this.stopPolling(id)
  }

  private async updateJob(id: string, data: any) {
    const job = this.jobs.get(id)
    if (!job) return

    // Parse the job status response
    const updatedJob: ManagedJob = {
      ...job,
      status: data.status || job.status,
      step: data.step || job.step,
      error: data.error || job.error,
      result: data.result || job.result,
      progress: this.calculateProgress(data.step, job.workflow),
      started_at: data.started_at || job.started_at,
      duration_seconds: data.duration_seconds || job.duration_seconds
    }

    // Update steps based on current step
    if (data.step) {
      updatedJob.steps = this.updateStepProgress(job.steps, data.step)
    }

    // Check if we should fetch the latest video for done jobs
    if (updatedJob.status === 'done' && !updatedJob.result) {
      try {
        const latestVideo = await getLatestManagedVideo(id)
        if (latestVideo && latestVideo.created_at && job.started_at) {
          const videoTime = new Date(latestVideo.created_at).getTime()
          const jobTime = new Date(job.started_at).getTime()
          if (videoTime >= jobTime) {
            updatedJob.result = latestVideo
            updatedJob.previewUrl = latestVideo.download_url
          }
        }
      } catch (e) {
        devLog('Failed to fetch latest video for completed job:', e)
      }
    }

    this.jobs.set(id, updatedJob)
    this.saveToLocalStorage()
    this.notifyListeners(updatedJob)
  }

  private calculateProgress(step: string | undefined, workflow: string): number {
    if (!step) return 0
    
    const steps = this.getWorkflowSteps(workflow)
    const stepIndex = steps.findIndex(s => s.key === step)
    if (stepIndex === -1) return 0
    
    return Math.round((stepIndex / steps.length) * 100)
  }

  private updateStepProgress(currentSteps: JobStep[], activeStep: string): JobStep[] {
    return currentSteps.map(step => ({
      ...step,
      done: this.isStepCompleted(step.key, activeStep, currentSteps),
      active: step.key === activeStep
    }))
  }

  private isStepCompleted(stepKey: string, activeStep: string, steps: JobStep[]): boolean {
    const stepIndex = steps.findIndex(s => s.key === stepKey)
    const activeIndex = steps.findIndex(s => s.key === activeStep)
    return stepIndex < activeIndex || (stepIndex === activeIndex && stepKey !== activeStep)
  }

  private getWorkflowSteps(workflow: string): JobStep[] {
    if (workflow === 'moneyprinter') {
      return [
        { key: 'validate_env', label: 'Validating Environment', done: false },
        { key: 'fetch_music', label: 'Fetching Background Music', done: false },
        { key: 'script_generation', label: 'Generating Script', done: false },
        { key: 'search_terms', label: 'Extracting Search Terms', done: false },
        { key: 'stock_download', label: 'Downloading Stock Footage', done: false },
        { key: 'tts', label: 'Generating Speech', done: false },
        { key: 'subtitles', label: 'Creating Subtitles', done: false },
        { key: 'compose_video', label: 'Composing Final Video', done: false }
      ]
    } else if (workflow === 'brainrot') {
      return [
        { key: 'process_video', label: 'Processing Video', done: false },
        { key: 'generate_compilations', label: 'Generating Compilations', done: false }
      ]
    }
    return []
  }

  // Resume capability checking
  async checkJobResumable(jobId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.apiBase}/api/jobs/${jobId}/resumable`)
      if (!response.ok) return false
      
      const data = await response.json()
      const job = this.jobs.get(jobId)
      if (job && data.can_resume) {
        job.canResume = true
        job.resumeInfo = {
          lastCompletedStep: data.next_step || '',
          completedSteps: 0, // Could be calculated from step info
          nextStep: data.next_step || ''
        }
        this.jobs.set(jobId, job)
        this.saveToLocalStorage()
        this.notifyListeners(job)
        return true
      }
      return false
    } catch (error) {
      devLog(`Failed to check resume capability for job ${jobId}:`, error)
      return false
    }
  }

  // Get job lineage (parent/child relationships for resumed jobs)
  async getJobLineage(jobId: string): Promise<{ ancestors: any[]; descendants: any[] } | null> {
    const cacheKey = jobId
    const cached = this.lineageCache.get(cacheKey)
    
    // Return cached result if less than 5 minutes old
    if (cached && (Date.now() - cached.fetchedAt) < 5 * 60 * 1000) {
      return { ancestors: cached.ancestors, descendants: cached.descendants }
    }

    try {
      const response = await fetch(`${this.apiBase}/api/jobs/${jobId}/lineage`)
      if (!response.ok) return null
      
      const data = await response.json()
      
      // Cache the result
      this.lineageCache.set(cacheKey, {
        ancestors: data.ancestors || [],
        descendants: data.descendants || [],
        fetchedAt: Date.now()
      })
      
      return {
        ancestors: data.ancestors || [],
        descendants: data.descendants || []
      }
    } catch (error) {
      devLog(`Failed to fetch lineage for job ${jobId}:`, error)
      return null
    }
  }

  // Download result
  async downloadResult(jobId: string): Promise<boolean> {
    const job = this.jobs.get(jobId)
    if (!job || !job.result) return false

    try {
      const downloadPath = downloadUrl(job.result.download_url || job.result.file_path)
      // Trigger download by creating a temporary link
      const link = document.createElement('a')
      link.href = downloadPath
      link.download = job.result.filename || `video_${jobId}.mp4`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      return true
    } catch (error) {
      console.error('Download failed:', error)
      return false
    }
  }

  // Cancel job
  async cancelJob(jobId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.apiBase}/api/jobs/${jobId}/cancel`, { method: 'POST' })
      if (response.ok) {
        const job = this.jobs.get(jobId)
        if (job) {
          job.status = 'cancelled'
          this.jobs.set(jobId, job)
          this.saveToLocalStorage()
          this.notifyListeners(job)
          this.stopPolling(jobId)
        }
        return true
      }
      return false
    } catch (error) {
      console.error('Cancel failed:', error)
      return false
    }
  }

  private loadFromLocalStorage() {
    try {
      const stored = localStorage.getItem('managedJobs')
      if (stored) {
        const jobsData = JSON.parse(stored)
        if (Array.isArray(jobsData)) {
          jobsData.forEach((jobData: any) => {
            const job: ManagedJob = {
              ...jobData,
              steps: jobData.steps || this.getWorkflowSteps(jobData.workflow)
            }
            this.jobs.set(job.id, job)
          })
          devLog(`JobManager: Loaded ${this.jobs.size} jobs from localStorage`)
        }
      }
    } catch (e) {
      devLog('Failed to load jobs from localStorage:', e)
    }
  }

  private saveToLocalStorage() {
    try {
      const jobsArray = Array.from(this.jobs.values())
      localStorage.setItem('managedJobs', JSON.stringify(jobsArray))
    } catch (e) {
      devLog('Failed to save jobs to localStorage:', e)
    }
  }

  private cleanupOldJobs() {
    const now = Date.now()
    const maxAge = 10 * 60 * 1000 // 10 minutes
    
    for (const [id, job] of this.jobs.entries()) {
      if (['done', 'error', 'cancelled'].includes(job.status)) {
        const age = now - job.createdAt
        if (age > maxAge) {
          devLog(`JobManager: Cleaning up old job ${id}`)
          this.removeJob(id)
        }
      }
    }
  }

  // Cleanup method
  cleanup() {
    devLog('JobManager: Cleaning up...')
    
    // Stop all polling
    this.pollingIntervals.forEach(intervalId => clearTimeout(intervalId))
    this.pollingIntervals.clear()
  }
}

// Singleton instance
let jobManagerInstance: JobManager | null = null

export function getJobManager(apiBase?: string): JobManager {
  if (!jobManagerInstance) {
    if (!apiBase) {
      throw new Error('apiBase is required for first initialization of JobManager')
    }
    jobManagerInstance = new JobManager(apiBase)
  }
  return jobManagerInstance
}

export { JobManager }