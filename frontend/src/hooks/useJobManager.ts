import { useEffect, useRef, useState } from 'react'
import { JobManager, type ManagedJob } from '@/lib/jobManager'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:9000'

export interface UseJobManagerReturn {
  jobs: ManagedJob[]
  initialized: boolean
  addJob: (id: string, workflow: 'moneyprinter' | 'brainrot', payload?: any) => void
  removeJob: (id: string) => void
  clearCompletedJobs: () => void
  getJob: (id: string) => ManagedJob | undefined
  hasActiveJobs: () => boolean
  getActiveJobs: () => ManagedJob[]
  validateAllJobs: () => Promise<number>
  cleanupLegacyJobs: () => Promise<void>
  getResumableJobs: () => Promise<ManagedJob[]>
  forceCleanup: () => Promise<void>
  fetchJobLineage: (id: string, options?: { force?: boolean }) => Promise<{ ancestors: any[]; descendants: any[] }>
}

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}

// Create a singleton JobManager instance
let jobManagerInstance: JobManager | null = null

function getJobManagerInstance(): JobManager {
  if (!jobManagerInstance) {
    devLog('useJobManager: Creating new JobManager singleton instance')
    jobManagerInstance = new JobManager(API_BASE)
  }
  return jobManagerInstance
}

export function useJobManager(): UseJobManagerReturn {
  const [jobs, setJobs] = useState<ManagedJob[]>([])
  const [initialized, setInitialized] = useState(false)
  const listenerRef = useRef<((job: ManagedJob) => void) | null>(null)

  // Initialize job manager
  useEffect(() => {
    devLog('useJobManager: Initializing hook instance')
    const jobManager = getJobManagerInstance()
    
    // Create listener for job updates
    const handleJobUpdate = (job: ManagedJob) => {
      devLog('useJobManager: Received job update', job);
      setJobs(prevJobs => {
        const existingIndex = prevJobs.findIndex(j => j.id === job.id)
        if (existingIndex >= 0) {
          const newJobs = [...prevJobs]
          newJobs[existingIndex] = job
          return newJobs
        } else {
          return [...prevJobs, job]
        }
      })
    }
    
    // Store the listener reference and add it
    listenerRef.current = handleJobUpdate
    jobManager.addListener(handleJobUpdate)
    
    // Set initial jobs state from the manager
    const currentJobs = jobManager.getAllJobs()
    devLog(`useJobManager: Setting initial jobs state with ${currentJobs.length} jobs`)
    setJobs(currentJobs)
    setInitialized(true)

    return () => {
      // Remove listener on cleanup
      devLog('useJobManager: Cleaning up hook instance')
      if (listenerRef.current) {
        jobManager.removeListener(listenerRef.current)
      }
    }
  }, [])

  const addJob = (
    id: string, 
    workflow: 'moneyprinter' | 'brainrot', 
    payload?: any
  ) => {
    devLog('useJobManager: addJob called with', { id, workflow, payload });
    const jobManager = getJobManagerInstance()
    
    // Create a new ManagedJob
    const newJob: ManagedJob = {
      id,
      workflow,
      status: 'queued',
      steps: workflow === 'moneyprinter' 
        ? [
            { key: 'validate_env', label: 'Validating Environment', done: false },
            { key: 'fetch_music', label: 'Fetching Background Music', done: false },
            { key: 'script_generation', label: 'Generating Script', done: false },
            { key: 'search_terms', label: 'Extracting Search Terms', done: false },
            { key: 'stock_download', label: 'Downloading Stock Footage', done: false },
            { key: 'tts', label: 'Generating Speech', done: false },
            { key: 'subtitles', label: 'Creating Subtitles', done: false },
            { key: 'compose_video', label: 'Composing Final Video', done: false }
          ]
        : [
            { key: 'process_video', label: 'Processing Video', done: false },
            { key: 'generate_compilations', label: 'Generating Compilations', done: false }
          ],
      createdAt: Date.now(),
      progress: 0,
      isNewlyCreated: true // Mark as newly created
    }
    
    jobManager.addJob(newJob)
  }

  const removeJob = (id: string) => {
    const jobManager = getJobManagerInstance()
    jobManager.removeJob(id)
    setJobs(prevJobs => prevJobs.filter(job => job.id !== id))
  }

  const clearCompletedJobs = () => {
    setJobs(prevJobs => prevJobs.filter(job => !['done', 'error', 'cancelled'].includes(job.status)))
  }

  const getJob = (id: string): ManagedJob | undefined => {
    const jobManager = getJobManagerInstance()
    return jobManager.getJob(id)
  }

  const hasActiveJobs = (): boolean => {
    return jobs.some(job => !['done', 'error', 'cancelled'].includes(job.status))
  }

  const getActiveJobs = (): ManagedJob[] => {
    return jobs.filter(job => !['done', 'error', 'cancelled'].includes(job.status))
  }

  const validateAllJobs = async (): Promise<number> => {
    // Validate jobs by checking their status on the server
    let removedCount = 0
    const jobManager = getJobManagerInstance()
    
    for (const job of jobs) {
      try {
        const response = await fetch(`${API_BASE}/api/jobs/${job.id}`)
        if (response.status === 404) {
          jobManager.removeJob(job.id)
          removedCount++
        }
      } catch (error) {
        devLog(`Failed to validate job ${job.id}:`, error)
      }
    }
    
    // Refresh the local jobs state after validation
    setJobs(jobManager.getAllJobs())
    return removedCount
  }

  const cleanupLegacyJobs = (): Promise<void> => {
    return new Promise((resolve) => {
      // Clear any legacy localStorage entries
      const legacyKeys = ['creator:lastJob', 'compilations:lastJob', 'creator:lastResult', 'compilations:lastResult']
      let removedCount = 0
      
      legacyKeys.forEach(key => {
        if (localStorage.getItem(key)) {
          localStorage.removeItem(key)
          removedCount++
          devLog(`useJobManager: Removed legacy key: ${key}`)
        }
      })
      
      if (removedCount > 0) {
        devLog(`useJobManager: Cleaned up ${removedCount} legacy localStorage entries`)
      }
      
      resolve()
    })
  }

  const getResumableJobs = async (): Promise<ManagedJob[]> => {
    const resumableJobs: ManagedJob[] = []
    
    for (const job of jobs) {
      if (['error', 'cancelled'].includes(job.status)) {
        const canResume = await checkJobResumable(job.id)
        if (canResume) {
          resumableJobs.push(job)
        }
      }
    }
    
    return resumableJobs
  }

  const checkJobResumable = async (jobId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${jobId}/resumable`)
      return response.ok
    } catch (error) {
      return false
    }
  }

  const forceCleanup = async (): Promise<void> => {
    const jobManager = getJobManagerInstance()
    
    // Remove all completed jobs
    const completedJobs = jobs.filter(job => ['done', 'error', 'cancelled'].includes(job.status))
    completedJobs.forEach(job => jobManager.removeJob(job.id))
    
    // Refresh the local jobs state after cleanup
    setJobs(jobManager.getAllJobs())
  }

  const fetchJobLineage = async (id: string, options?: { force?: boolean }): Promise<{ ancestors: any[]; descendants: any[] }> => {
    const jobManager = getJobManagerInstance()
    const lineage = await jobManager.getJobLineage(id)
    return lineage || { ancestors: [], descendants: [] }
  }

  return {
    jobs,
    initialized,
    addJob,
    removeJob,
    clearCompletedJobs,
    getJob,
    hasActiveJobs,
    getActiveJobs,
    validateAllJobs,
    cleanupLegacyJobs,
    getResumableJobs,
    forceCleanup,
    fetchJobLineage,
  }
}
