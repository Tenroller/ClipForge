import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { Button } from '@/components/components/ui/button'
import { FaEye, FaRedo, FaSpinner } from 'react-icons/fa'
import { listJobs, remakeJob, type JobRecord } from '@/lib/api'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'
import ResultPanel from '@/components/ResultPanel'
import ResumableJobsPanel from '@/components/ResumableJobsPanel'

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}

export default function ActivityPage() {
  const [serverJobs, setServerJobs] = useState<JobRecord[]>([])
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const [remakingJobs, setRemakingJobs] = useState<Set<string>>(new Set())
  const jobManager = useJobManager()

  useEffect(() => {
    // Fetch server jobs from API
    (async () => {
      try {
        const js = await listJobs(50)
        setServerJobs(js)
      } catch {}
    })()
  }, [])

  const handleViewResult = (job: ManagedJob) => {
    setSelectedResult(job)
  }

  const handleCloseResult = () => {
    setSelectedResult(null)
  }

  const handleRemakeJob = async (jobId: string) => {
    try {
      setRemakingJobs(prev => new Set(prev.add(jobId)))
      const result = await remakeJob(jobId)
      
      // Refresh the jobs list to show the new job
      const updatedJobs = await listJobs(50)
      setServerJobs(updatedJobs)
      
      // Show success message (you could add a toast notification here)
      devLog(`Job remade successfully: ${result.job_id}`)
      
    } catch (error) {
      console.error('Failed to remake job:', error)
      alert(`Failed to remake job: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setRemakingJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  const canRemakeJob = (job: JobRecord) => {
    // Can remake jobs that are done, error, or cancelled and have request_data
    return ['done', 'error', 'cancelled'].includes(job.status) && job.request_data
  }

  // If showing results, render the result panel
  if (selectedResult) {
    return (
      <div className="container-page fade-in max-w-[1200px]">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    )
  }

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <div className="space-y-6">
        {/* Resumable Jobs Panel */}
        <ResumableJobsPanel jobManager={jobManager} />
        
        {/* Regular Activity Card */}
        <Card className="enhanced-card">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-5">
              <div>
                <div className="text-xs text-muted-foreground mb-2">Server jobs</div>
                {serverJobs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No server jobs</div>
                ) : serverJobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-[10px] uppercase">{j.workflow}</Badge>
                      <div className="text-sm font-medium">{j.id}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={j.status === 'done' ? 'default' : j.status === 'error' ? 'destructive' : 'secondary'}>{j.status}</Badge>
                      {canRemakeJob(j) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemakeJob(j.id)}
                          disabled={remakingJobs.has(j.id)}
                          className="h-7 px-2 text-xs"
                          title="Remake with same parameters"
                        >
                          {remakingJobs.has(j.id) ? (
                            <FaSpinner className="size-3 mr-1 animate-spin" />
                          ) : (
                            <FaRedo className="size-3 mr-1" />
                          )}
                          Remake
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-2">Managed jobs ({jobManager.jobs.length})</div>
                {jobManager.jobs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No managed jobs</div>
                ) : jobManager.jobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-[10px] uppercase">{j.workflow}</Badge>
                      <div className="text-sm font-medium">{j.id}</div>
                      <div className="text-xs text-muted-foreground">
                        {j.progress}% - {j.step || 'Initializing...'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={j.status === 'done' ? 'default' : j.status === 'error' ? 'destructive' : 'secondary'}>{j.status}</Badge>
                      {j.status === 'done' && j.previewUrl && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleViewResult(j)}
                          className="h-7 px-2 text-xs"
                        >
                          <FaEye className="size-3 mr-1" />
                          View
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}


