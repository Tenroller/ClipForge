import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { 
  FaTimes, 
  FaDownload, 
  FaCheckCircle, 
  FaClock,
  FaExternalLinkAlt,
  FaCopy,
  FaCheck
} from "react-icons/fa"
import type { JobRecord } from "@/lib/api"
import { formatDuration as formatDurationLib } from "@/lib/formatDuration"

interface ResultPanelProps {
  job: JobRecord
  onClose: () => void
}

function formatDuration(startTime: number, endTime?: number): string {
  const duration = (endTime || Date.now()) - startTime
  const seconds = Math.floor(duration / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  } else {
    return `${seconds}s`
  }
}

function getWorkflowLabel(workflow: string): string {
  switch (workflow) {
    case 'moneyprinter':
      return 'AI Video Generation'
    case 'brainrot':
      return 'Video Compilation'
    default:
      return workflow
  }
}

export default function ResultPanel({ job, onClose }: ResultPanelProps) {
  const [copied, setCopied] = useState(false)

  const copyJobId = async () => {
    try {
      await navigator.clipboard.writeText(job.id)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy job ID:', err)
    }
  }

  const completedSteps = 0 // job.steps?.filter(s => s.done).length ?? 0
  const totalSteps = 0 // job.steps?.length ?? 0

  return (
    <div className="result-panel-enter">
      <Card className="enhanced-card result-success border-l-4 border-l-green-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 flex items-center justify-center">
                <FaCheckCircle className="size-4 text-white" />
              </div>
              <div>
                <div>Video Generated Successfully</div>
                <p className="text-sm font-normal text-muted-foreground">
                  {getWorkflowLabel(job.workflow)} completed
                </p>
              </div>
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 h-8 w-8"
            >
              <FaTimes className="size-4" />
            </Button>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {/* Video Preview */}
          {job.output_url && (
            <div className="relative">
              <video 
                src={job.output_url} 
                controls 
                className="video-frame w-full max-h-[400px] rounded-lg shadow-lg" 
                poster="/api/placeholder/640/360"
                preload="metadata"
              />
            </div>
          )}

          {/* Job Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-muted/30 border">
                <div className="text-xs text-muted-foreground mb-1">Job ID</div>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono">{job.id.substring(0, 16)}...</code>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyJobId}
                    className="p-1 h-6 w-6"
                  >
                    {copied ? <FaCheck className="size-3 text-green-600" /> : <FaCopy className="size-3" />}
                  </Button>
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted/30 border">
                <div className="text-xs text-muted-foreground mb-1">Workflow</div>
                <Badge variant="outline" className="text-xs">
                  {getWorkflowLabel(job.workflow)}
                </Badge>
              </div>
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-muted/30 border">
                <div className="text-xs text-muted-foreground mb-1">Processing Time</div>
                <div className="flex items-center gap-2 text-sm">
                  <FaClock className="size-3" />
                  {job.duration_seconds ? formatDurationLib(job.duration_seconds) : formatDuration(job.createdAt ?? Date.now())}
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted/30 border">
                <div className="text-xs text-muted-foreground mb-1">Steps Completed</div>
                <div className="text-sm font-medium">
                  {completedSteps} of {totalSteps} steps
                </div>
              </div>
              
              {job.duration_seconds && (
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800">
                  <div className="text-xs text-muted-foreground mb-1">Generation Time</div>
                  <div className="text-sm font-medium text-blue-900 dark:text-blue-100">
                    {formatDurationLib(job.duration_seconds)}
                  </div>
                  {job.duration_seconds > 300 && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                      Complex videos take longer to process
                    </div>
                  )}
                  {job.duration_seconds < 60 && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                      Fast generation! ⚡
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Processing Steps Summary */}
          <div className="p-4 rounded-lg bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20 border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-3 mb-3">
              <div className="size-6 rounded-full bg-green-500 flex items-center justify-center">
                <FaCheckCircle className="size-3 text-white" />
              </div>
              <div>
                <div className="font-medium text-green-800 dark:text-green-200 text-sm">
                  All steps completed successfully
                </div>
                <div className="text-xs text-green-600 dark:text-green-400">
                  Your video is ready for download
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              onClick={onClose}
              variant="outline"
              className="flex-1 sm:flex-initial"
            >
              Create Another Video
            </Button>
            
            {job.output_url && (
              <div className="flex gap-2 flex-1">
                <Button
                  asChild
                  variant="default"
                  className="flex-1"
                >
                  <a 
                    href={job.output_url} 
                    download 
                    target="_blank" 
                    rel="noreferrer"
                    className="flex items-center gap-2"
                  >
                    <FaDownload className="size-4" />
                    Download Video
                  </a>
                </Button>
                
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  className="px-3"
                >
                  <a 
                    href={job.output_url} 
                    target="_blank" 
                    rel="noreferrer"
                  >
                    <FaExternalLinkAlt className="size-4" />
                  </a>
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
