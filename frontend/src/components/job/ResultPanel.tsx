import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  X,
  Download,
  CheckCircle,
  Clock,
  ExternalLink,
  Copy,
  Check,
  Video
} from "lucide-react"
import type { JobRecord } from "@/lib/api"
import { formatDuration as formatDurationLib } from "@/lib/formatDuration"
import { downloadUrl } from "@/lib/api"

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
    case 'podcastclips':
      return 'Podcast Clips'
    default:
      return workflow
  }
}

export default function ResultPanel({ job, onClose }: ResultPanelProps) {
  const [copied, setCopied] = useState(false)

  // Helper to safely extract clips data from job result
  const getClipsData = () => {
    if (job.result && typeof job.result === 'object' && 'clips_count' in job.result) {
      const result = job.result as { clips_count?: unknown; output_files?: unknown };
      return {
        clips_count: typeof result.clips_count === 'number' ? result.clips_count : 0,
        output_files: Array.isArray(result.output_files) ? result.output_files : []
      };
    }
    return { clips_count: 0, output_files: [] };
  };

  const clipsData = getClipsData();

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
    <div>
      <Card className="border-l-4 border-l-green-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-green-500 flex items-center justify-center">
                <CheckCircle className="size-4 text-white" />
              </div>
              <div>
                <div>
                  {job.workflow === 'podcastclips' && clipsData.clips_count > 0
                    ? `${clipsData.clips_count} Clips Generated Successfully`
                    : 'Video Generated Successfully'}
                </div>
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
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {/* Video Preview - Single Video */}
          {job.output_url && job.workflow !== 'podcastclips' && (
            <div className="relative">
              <video
                src={job.output_url}
                controls
                className="w-full max-h-[400px] rounded-lg border bg-black"
                poster="/api/placeholder/640/360"
                preload="metadata"
              />
            </div>
          )}

          {/* Podcast Clips - Multiple Videos */}
          {job.workflow === 'podcastclips' && clipsData.clips_count > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Video className="size-5 text-purple-500" />
                <h3 className="text-lg font-semibold">
                  Generated {clipsData.clips_count} Viral Clips
                </h3>
              </div>
              
              {/* Grid of clips */}
              <div className="space-y-2">
                {clipsData.output_files.map((filePath: string, index: number) => {
                  const fileName = filePath.split('/').pop() || `Clip ${index + 1}`;
                  const downloadLink = downloadUrl(filePath);

                  return (
                    <Card key={index} className="overflow-hidden border-muted">
                      <CardContent className="p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <div className="size-10 rounded-lg bg-purple-500 flex items-center justify-center shrink-0">
                              <Video className="size-4 text-white" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium truncate">{fileName}</p>
                              <p className="text-xs text-muted-foreground">Clip {index + 1}</p>
                            </div>
                          </div>
                          <div className="flex gap-2 shrink-0">
                            <Button
                              asChild
                              variant="outline"
                              size="sm"
                            >
                              <a
                                href={downloadLink}
                                download
                                className="flex items-center gap-2"
                              >
                                <Download className="size-3" />
                                Download
                              </a>
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Job Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">Job ID</div>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono">{job.id.substring(0, 16)}...</code>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyJobId}
                    className="p-1 h-6 w-6"
                  >
                    {copied ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
                  </Button>
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">Workflow</div>
                <Badge variant="outline" className="text-xs">
                  {getWorkflowLabel(job.workflow)}
                </Badge>
              </div>
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">Processing Time</div>
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="size-3" />
                  {job.duration_seconds ? formatDurationLib(job.duration_seconds) : formatDuration(job.createdAt ?? 0)}
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">Steps Completed</div>
                <div className="text-sm font-medium">
                  {completedSteps} of {totalSteps} steps
                </div>
              </div>
              
              {job.duration_seconds && (
                <div className="p-3 rounded-lg bg-muted border">
                  <div className="text-xs text-muted-foreground mb-1">Generation Time</div>
                  <div className="text-sm font-medium">
                    {formatDurationLib(job.duration_seconds)}
                  </div>
                  {job.duration_seconds > 300 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      Complex videos take longer to process
                    </div>
                  )}
                  {job.duration_seconds < 60 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      Fast generation!
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Processing Steps Summary */}
          <div className="p-4 rounded-lg bg-muted border">
            <div className="flex items-center gap-3 mb-3">
              <div className="size-6 rounded-full bg-green-500 flex items-center justify-center">
                <CheckCircle className="size-3 text-white" />
              </div>
              <div>
                <div className="font-medium text-sm">
                  All steps completed successfully
                </div>
                <div className="text-xs text-muted-foreground">
                  {job.workflow === 'podcastclips' && clipsData.clips_count > 0
                    ? `Your ${clipsData.clips_count} clips are ready for download`
                    : 'Your video is ready for download'}
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
              {job.workflow === 'podcastclips' ? 'Create More Clips' : 'Create Another Video'}
            </Button>

            {/* Download button for single video workflows */}
            {job.output_url && job.workflow !== 'podcastclips' && (
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
                    <Download className="size-4" />
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
                    <ExternalLink className="size-4" />
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
