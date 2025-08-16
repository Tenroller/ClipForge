import { useEffect, useRef, useState } from 'react'
import JobManager, { type ManagedJob } from '@/lib/jobManager'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

// Create a singleton JobManager instance
let jobManagerInstance: JobManager | null = null

function getJobManagerInstance(): JobManager {
  if (!jobManagerInstance) {
    console.log('useJobManager: Creating new JobManager singleton instance')
    jobManagerInstance = new JobManager(API_BASE)
    // Load persisted jobs on first initialization
    jobManagerInstance.loadFromLocalStorage()
  }
  return jobManagerInstance
}

export function useJobManager() {
  const [jobs, setJobs] = useState<ManagedJob[]>([])
  const [initialized, setInitialized] = useState(false)
  const listenerRef = useRef<((job: ManagedJob) => void) | null>(null)

  // Initialize job manager
  useEffect(() => {
    console.log('useJobManager: Initializing hook instance')
    const jobManager = getJobManagerInstance()
    
    // Create listener for job updates
    const handleJobUpdate = (job: ManagedJob) => {
      console.log('useJobManager: Received job update', job);
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
    console.log(`useJobManager: Setting initial jobs state with ${currentJobs.length} jobs`)
    setJobs(currentJobs)
    setInitialized(true)

    return () => {
      // Remove listener on cleanup
      console.log('useJobManager: Cleaning up hook instance')
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
    console.log('useJobManager: addJob called with', { id, workflow, payload });
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
          console.log(`useJobManager: Removed legacy key: ${key}`)
        }
      })
      
      if (removedCount > 0) {
        console.log(`useJobManager: Cleaned up ${removedCount} legacy localStorage entries`)
      }
      
      resolve()
    })
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
  }
}
