import React, { useState, useEffect } from 'react'
import { Button } from '@/components/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { FaRedo, FaPlay, FaExclamationTriangle, FaCheckCircle, FaClock } from 'react-icons/fa'
import { ManagedJob } from '@/lib/jobManager'

interface ResumableJobsPanelProps {
  jobManager: any
  onJobResumed?: (jobId: string) => void
}

export default function ResumableJobsPanel({ jobManager, onJobResumed }: ResumableJobsPanelProps) {
  const [resumableJobs, setResumableJobs] = useState<ManagedJob[]>([])
  const [loading, setLoading] = useState(false)
  const [resumingJobs, setResumingJobs] = useState<Set<string>>(new Set())

  const loadResumableJobs = async () => {
    setLoading(true)
    try {
      const jobs = await jobManager.getResumableJobs()
      setResumableJobs(jobs)
    } catch (error) {
      console.error('Failed to load resumable jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleResumeJob = async (jobId: string) => {
    setResumingJobs(prev => new Set(prev).add(jobId))
    
    try {
      const success = await jobManager.resumeJob(jobId)
      if (success) {
        // Remove from resumable list and refresh
        setResumableJobs(prev => prev.filter(job => job.id !== jobId))
        onJobResumed?.(jobId)
      } else {
        // Show error or refresh the list
        await loadResumableJobs()
      }
    } catch (error) {
      console.error('Failed to resume job:', error)
    } finally {
      setResumingJobs(prev => {
        const next = new Set(prev)
        next.delete(jobId)
        return next
      })
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'error':
        return <FaExclamationTriangle className="h-4 w-4 text-red-500" />
      case 'cancelled':
        return <FaClock className="h-4 w-4 text-orange-500" />
      default:
        return <FaCheckCircle className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'error':
        return <Badge variant="destructive">Failed</Badge>
      case 'cancelled':
        return <Badge variant="secondary">Cancelled</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleString()
  }

  const getWorkflowName = (workflow: string) => {
    switch (workflow) {
      case 'moneyprinter':
        return 'AI Video Generator'
      case 'brainrot':
        return 'Brainrot Compilation'
      default:
        return workflow
    }
  }

  useEffect(() => {
    loadResumableJobs()
  }, [])

  if (loading && resumableJobs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
                          <FaRedo className="h-5 w-5 animate-spin" />
            Loading resumable jobs...
          </CardTitle>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Resume Interrupted Jobs</h3>
          <p className="text-sm text-muted-foreground">
            Restart video generation from where it was interrupted
          </p>
        </div>
        <Button 
          variant="outline" 
          onClick={loadResumableJobs}
          disabled={loading}
        >
                          <FaRedo className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {resumableJobs.length === 0 ? (
        <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg">
                          <FaCheckCircle className="h-4 w-4 text-green-600" />
          <span className="text-green-800">
            No resumable jobs found. Jobs that fail or are cancelled will appear here if they can be resumed.
          </span>
        </div>
      ) : (
        <div className="space-y-3">
          {resumableJobs.map((job) => (
            <Card key={job.id} className="relative">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(job.status)}
                    <div>
                      <CardTitle className="text-base">
                        {getWorkflowName(job.workflow)}
                      </CardTitle>
                      <CardDescription className="text-sm">
                        Job ID: {job.id.slice(0, 8)}...
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(job.status)}
                    <Button
                      size="sm"
                      onClick={() => handleResumeJob(job.id)}
                      disabled={resumingJobs.has(job.id)}
                    >
                      {resumingJobs.has(job.id) ? (
                        <FaRedo className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                                                  <FaPlay className="h-4 w-4 mr-2" />
                      )}
                      Resume
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {job.resumeInfo && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Last completed:</span>
                        <br />
                        <span className="text-muted-foreground">
                          {job.resumeInfo.lastCompletedStep.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div>
                        <span className="font-medium">Progress:</span>
                        <br />
                        <span className="text-muted-foreground">
                          {job.resumeInfo.completedSteps} steps completed
                        </span>
                      </div>
                      <div>
                        <span className="font-medium">Next step:</span>
                        <br />
                        <span className="text-muted-foreground">
                          {job.resumeInfo.nextStep.replace(/_/g, ' ')}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {job.error && (
                    <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                      <FaExclamationTriangle className="h-4 w-4 text-red-600" />
                      <span className="text-red-800 text-sm">
                        <strong>Error:</strong> {job.error}
                      </span>
                    </div>
                  )}
                  
                  <div className="text-xs text-muted-foreground">
                    Last updated: {formatDate(job.createdAt)}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
