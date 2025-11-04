import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { Button } from '@/components/components/ui/button'
import { Progress } from '@/components/components/ui/progress'
// import { ScrollArea } from '@/components/components/ui/scroll-area'
import { Separator } from '@/components/components/ui/separator'
import { 
  FaArrowLeft, 
  FaSpinner, 
  FaCheckCircle, 
  FaTimesCircle, 
  FaPause, 
  FaClock,
  FaPlay,
  FaEye,
  FaDownload,
  FaRedo
} from 'react-icons/fa'
import { formatDuration } from '@/lib/formatDuration'
import { toast } from 'sonner'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'
import JobLineagePanel from '@/components/JobLineagePanel'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:9000'

type LogEntry = {
  timestamp: string
  level: string
  source: string
  message: string
}

type JobLogs = {
  job_id: string
  logs: LogEntry[]
  total_logs: number
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'queued':
      return <FaClock className="size-4" />
    case 'running':
      return <FaSpinner className="size-4 animate-spin" />
    case 'done':
      return <FaCheckCircle className="size-4 text-green-600" />
    case 'error':
      return <FaTimesCircle className="size-4 text-red-600" />
    case 'cancelled':
      return <FaPause className="size-4 text-gray-600" />
    default:
      return <FaPlay className="size-4" />
  }
}

function getStatusColor(status: string): "secondary" | "default" | "destructive" | "outline" {
  switch (status) {
    case 'queued':
      return 'secondary'
    case 'running':
      return 'default'
    case 'done':
      return 'default' // Changed from 'success' to 'default'
    case 'error':
      return 'destructive'
    case 'cancelled':
      return 'secondary'
    default:
      return 'outline'
  }
}

function formatTimestamp(timestamp: string) {
  try {
    return new Date(timestamp).toLocaleString()
  } catch {
    return timestamp
  }
}

function getLevelColor(level: string) {
  switch (level.toLowerCase()) {
    case 'error':
      return 'text-red-600 bg-red-50 dark:bg-red-950/20'
    case 'warning':
    case 'warn':
      return 'text-yellow-600 bg-yellow-50 dark:bg-yellow-950/20'
    case 'debug':
      return 'text-gray-500 bg-gray-50 dark:bg-gray-950/20'
    case 'info':
    default:
      return 'text-blue-600 bg-blue-50 dark:bg-blue-950/20'
  }
}

export default function JobMonitoringPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const jobManager = useJobManager()
  const [job, setJob] = useState<ManagedJob | null>(null)
  const [logs, setLogs] = useState<JobLogs | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Initial fetch
  useEffect(() => {
    if (!jobId) return
    const existing = jobManager.getJob(jobId)
    if (existing) {
      setJob(existing)
      setLoading(false)
    } else {
      fetchJobDetails()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // Auto refresh job details (includes logs when backend is updated)
  useEffect(() => {
    if (!autoRefresh || !job || ['done', 'error', 'cancelled'].includes(job.status)) return
    const interval = setInterval(() => {
      fetchJobDetails()
    }, 2000)
    return () => clearInterval(interval)
  }, [autoRefresh, job?.status])

  // Additional periodic logs refresh for current backend (will be redundant when backend is updated)
  useEffect(() => {
    if (!autoRefresh || !job || ['done', 'error', 'cancelled'].includes(job.status)) return
    
    // Only fetch logs separately if we don't have recent logs from job status
    const needsSeparateLogsRefresh = !logs || logs.logs.length === 0
    
    if (needsSeparateLogsRefresh) {
      const logsInterval = setInterval(() => {
        fetchJobLogsFromSeparateEndpoint()
      }, 3000) // Slightly less frequent than job details
      
      return () => clearInterval(logsInterval)
    }
  }, [autoRefresh, job?.status, logs])

  const fetchJobDetails = async () => {
    if (!jobId) return
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${jobId}`)
      if (!response.ok) {
        if (response.status === 404) {
          toast.error('Job not found')
          navigate('/activity')
          return
        }
        throw new Error(`HTTP ${response.status}`)
      }
      const jobData = await response.json()
      const managedJob: ManagedJob = {
        id: jobData.id,
        workflow: jobData.workflow || 'unknown',
        status: jobData.status,
        step: jobData.step,
        steps: getInitialSteps(jobData.workflow || 'unknown'),
        result: jobData.result,
        error: jobData.error,
        createdAt: new Date(jobData.created_at || Date.now()).getTime(),
        progress: calculateProgress(jobData.step, jobData.status),
        started_at: jobData.started_at,
        duration_seconds: jobData.duration_seconds
      }

      // Check if job status response includes logs (optimized API)
      const hasLogsInResponse = jobData.logs && Array.isArray(jobData.logs)
      const hasEnhancedLogs = hasLogsInResponse && (jobData.total_logs !== undefined || jobData.logs.length > 0)
      
      if (hasEnhancedLogs) {
        // Use logs from job status response (optimized path)
        const logsData: JobLogs = {
          job_id: jobData.id,
          logs: jobData.logs,
          total_logs: jobData.total_logs || jobData.logs.length
        }
        setLogs(logsData)
      } else if (hasLogsInResponse && jobData.logs.length === 0) {
        // Job status has empty logs array - fetch from separate endpoint
        await fetchJobLogsFromSeparateEndpoint()
      }

      setJob(managedJob)
    } catch (error) {
      console.error('Failed to fetch job details:', error)
      toast.error('Failed to load job details')
    } finally {
      setLoading(false)
    }
  }

  const fetchJobLogsFromSeparateEndpoint = async () => {
    if (!jobId) return

    try {
      const response = await fetch(`${API_BASE}/api/jobs/${jobId}/logs`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const logsData = await response.json()
      setLogs(logsData)
    } catch (error) {
      console.error('Failed to fetch job logs from separate endpoint:', error)
      // Don't show error toast for logs - just log it
    }
  }

  const getInitialSteps = (workflow: string) => {
    if (workflow === 'brainrot') {
      return [
        { key: 'download_video', label: 'Download Video', done: false },
        { key: 'extract_audio', label: 'Extract Audio', done: false },
        { key: 'segment_audio', label: 'Segment Audio', done: false },
        { key: 'generate_clips', label: 'Generate Clips', done: false },
        { key: 'compile_videos', label: 'Compile Videos', done: false },
        { key: 'done', label: 'Complete', done: false }
      ]
    } else {
      return [
        { key: 'script', label: 'Generate Script', done: false },
        { key: 'voice', label: 'Generate Voice', done: false },
        { key: 'music', label: 'Add Music', done: false },
        { key: 'video', label: 'Generate Video', done: false },
        { key: 'subtitles', label: 'Add Subtitles', done: false },
        { key: 'combine', label: 'Combine Media', done: false },
        { key: 'upload', label: 'Upload', done: false },
        { key: 'done', label: 'Complete', done: false }
      ]
    }
  }

  const calculateProgress = (currentStep?: string, status?: string) => {
    if (status === 'done') return 100
    if (status === 'error' || status === 'cancelled') return 0
    if (!currentStep) return 0
    
    const steps = getInitialSteps(job?.workflow || 'unknown')
    const currentIndex = steps.findIndex(s => s.key === currentStep)
    return currentIndex >= 0 ? Math.round(((currentIndex + 1) / steps.length) * 100) : 0
  }

  const formatJobDuration = () => {
    if (job?.duration_seconds) {
      return formatDuration(job.duration_seconds)
    } else if (job?.started_at) {
      const startTime = new Date(job.started_at).getTime()
      const currentTime = Date.now()
      const durationSeconds = Math.floor((currentTime - startTime) / 1000)
      return formatDuration(durationSeconds)
    }
    return 'N/A'
  }

  const handleViewResult = () => {
    if (job?.result) {
      // Navigate back to the appropriate page with result view
      if (job.workflow === 'brainrot') {
        navigate('/compilations')
      } else {
        navigate('/creator')
      }
      toast.success('Redirected to view results')
    }
  }

  if (loading) {
    return (
      <div className="container-page fade-in">
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="text-center">
            <FaSpinner className="size-8 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">Loading job details...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container-page fade-in">
        <div className="text-center py-12">
          <FaTimesCircle className="size-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Job Not Found</h2>
          <p className="text-muted-foreground mb-6">
            The job you're looking for doesn't exist or has been removed.
          </p>
          <Button onClick={() => navigate('/activity')}>
            <FaArrowLeft className="size-4 mr-2" />
            Back to Activity
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="container-page fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/activity')}
            className="flex items-center gap-2"
          >
            <FaArrowLeft className="size-4" />
            Back to Activity
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Job Monitor</h1>
            <p className="text-sm text-muted-foreground">
              {job.workflow === 'brainrot' ? 'Brainrot Compilation' : 'AI Video Generation'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={autoRefresh ? 'bg-green-50 border-green-200' : ''}
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </Button>
          
          {job.status === 'done' && job.result && (
            <Button onClick={handleViewResult} className="flex items-center gap-2">
              <FaEye className="size-4" />
              View Result
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Job Status Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              {getStatusIcon(job.status)}
              Job Status
            </CardTitle>
            <CardDescription>
              Job ID: <code className="bg-muted px-2 py-1 rounded text-sm">{job.id}</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status:</span>
              <Badge variant={getStatusColor(job.status)}>
                {job.status}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Workflow:</span>
              <Badge variant="outline">
                {job.workflow === 'brainrot' ? 'Brainrot Compilation' : 'AI Video Generation'}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Duration:</span>
              <span className="text-sm font-mono">{formatJobDuration()}</span>
            </div>

            {job.step && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Current Step:</span>
                <span className="text-sm font-medium">{job.step.replace(/_/g, ' ')}</span>
              </div>
            )}

            <Separator />

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Progress</span>
                <span className="font-medium">{job.progress}%</span>
              </div>
              <Progress value={job.progress} className="h-2" />
            </div>

            {job.error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-950/20 dark:border-red-800/30">
                <p className="text-sm text-red-700 dark:text-red-300">
                  <strong>Error:</strong> {job.error}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Steps Progress Card */}
        <Card>
          <CardHeader>
            <CardTitle>Processing Steps</CardTitle>
            <CardDescription>
              Step-by-step progress through the {job.workflow} workflow
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {job.steps.map((step, index) => {
                const isActive = step.key === job.step && job.status === 'running'
                const isDone = step.done || (job.status === 'done' && step.key === 'done')
                
                return (
                  <div
                    key={step.key}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                      isDone
                        ? 'bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800/30'
                        : isActive
                        ? 'bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800/30'
                        : 'bg-muted/30 border-border/50'
                    }`}
                  >
                    <div className={`size-6 rounded-full border-2 flex items-center justify-center ${
                      isDone
                        ? 'bg-green-500 border-green-500 text-white'
                        : isActive
                        ? 'bg-blue-500 border-blue-500 text-white'
                        : 'border-muted-foreground/30 bg-background'
                    }`}>
                      {isDone ? (
                        <FaCheckCircle className="size-3" />
                      ) : isActive ? (
                        <FaSpinner className="size-3 animate-spin" />
                      ) : (
                        <span className="text-xs font-medium">{index + 1}</span>
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-sm">{step.label}</div>
                      {isActive && (
                        <div className="text-xs text-blue-600 dark:text-blue-400">
                          Processing...
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Lineage + Logs */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <JobLineagePanel jobId={job.id} jobManager={jobManager} />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Job Logs</span>
              <div className="flex items-center gap-2">
                {loading && <FaSpinner className="size-4 animate-spin" />}
                <Badge variant="secondary">
                  {job?.total_logs || logs?.total_logs || job?.logs?.length || 0} entries
                </Badge>
              </div>
            </CardTitle>
            <CardDescription>
              Real-time logs from the job execution and backend processing
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[400px] w-full rounded border bg-muted/20 p-4 overflow-auto">
              {(logs?.logs && logs.logs.length > 0) || (job?.logs && job.logs.length > 0) ? (
                <div className="space-y-2">
                  {/* Use logs from job first, fallback to separate logs state */}
                  {(job?.logs || logs?.logs || []).map((log, index) => (
                    <div key={index} className="text-sm font-mono">
                      <div className={`inline-block px-2 py-1 rounded text-xs font-semibold mr-2 ${getLevelColor(log.level)}`}>
                        {log.level.toUpperCase()}
                      </div>
                      <span className="text-muted-foreground mr-2">
                        [{formatTimestamp(log.timestamp)}]
                      </span>
                      <span className="text-xs text-muted-foreground mr-2">
                        ({log.source})
                      </span>
                      <span>{log.message}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  {loading ? (
                    <div className="flex items-center justify-center gap-2">
                      <FaSpinner className="size-4 animate-spin" />
                      <span>Loading logs...</span>
                    </div>
                  ) : (
                    <span>No logs available for this job</span>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
