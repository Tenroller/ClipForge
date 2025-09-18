import { useEffect, useRef, useState } from 'react'
import JobManager, { type ManagedJob } from '@/lib/jobManager'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

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
    // Load persisted jobs on first initialization
    jobManagerInstance.loadFromLocalStorage()
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
    jobManager.addJob(id, workflow, payload)
  }

  const removeJob = (id: string) => {
    const jobManager = getJobManagerInstance()
    jobManager.removeJob(id)
    setJobs(prevJobs => prevJobs.filter(job => job.id !== id))
  }

  const clearCompletedJobs = () => {
    const jobManager = getJobManagerInstance()
    jobManager.clearCompletedJobs()
    setJobs(jobManager.getAllJobs())
  }

  const getJob = (id: string): ManagedJob | undefined => {
    const jobManager = getJobManagerInstance()
    return jobManager.getJob(id)
  }

  const hasActiveJobs = (): boolean => {
    const jobManager = getJobManagerInstance()
    return jobManager.hasActiveJobs()
  }

  const getActiveJobs = (): ManagedJob[] => {
    const jobManager = getJobManagerInstance()
    return jobManager.getActiveJobs()
  }

  const validateAllJobs = async (): Promise<number> => {
    const jobManager = getJobManagerInstance()
    const removedCount = await jobManager.validateAllJobs()
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
    const jobManager = getJobManagerInstance()
    return jobManager.getResumableJobs()
  }

  const forceCleanup = async (): Promise<void> => {
    const jobManager = getJobManagerInstance()
    await jobManager.forceCleanup()
    // Refresh the local jobs state after cleanup
    setJobs(jobManager.getAllJobs())
  }

  const fetchJobLineage = async (id: string, options?: { force?: boolean }): Promise<{ ancestors: any[]; descendants: any[] }> => {
    const jobManager = getJobManagerInstance()
    return jobManager.fetchJobLineage(id, options)
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
