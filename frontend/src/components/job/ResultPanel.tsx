import { useState } from "react"
import { useTranslations } from "next-intl"
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
import { formatDuration, formatDurationFromTimestamps } from "@/lib/formatDuration"
import { downloadUrl } from "@/lib/api"

interface ResultPanelProps {
  job: JobRecord
  onClose: () => void
}

export default function ResultPanel({ job, onClose }: ResultPanelProps) {
  const [copied, setCopied] = useState(false)
  const t = useTranslations('resultPanel')

  const getWorkflowLabel = (workflow: string): string => {
    switch (workflow) {
      case 'moneyprinter':
        return t('workflowMoneyprinter')
      case 'brainrot':
        return t('workflowBrainrot')
      case 'podcastclips':
        return t('workflowPodcastclips')
      default:
        return workflow
    }
  }

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
      <Card className="border-l-4 border-l-success">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-success flex items-center justify-center">
                <CheckCircle className="size-4 text-white" />
              </div>
              <div>
                <div>
                  {job.workflow === 'podcastclips' && clipsData.clips_count > 0
                    ? t('clipsGeneratedTitle', { count: clipsData.clips_count })
                    : t('videoGeneratedTitle')}
                </div>
                <p className="text-sm font-normal text-muted-foreground">
                  {t('workflowCompleted', { workflow: getWorkflowLabel(job.workflow) })}
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
                <Video className="size-5 text-accent" />
                <h3 className="text-lg font-semibold">
                  {t('generatedViralClips', { count: clipsData.clips_count })}
                </h3>
              </div>
              
              {/* Grid of clips */}
              <div className="space-y-2">
                {clipsData.output_files.map((filePath: string, index: number) => {
                  const fileName = filePath.split('/').pop() || t('clipFallbackName', { number: index + 1 });
                  const downloadLink = downloadUrl(filePath);

                  return (
                    <Card key={index} className="overflow-hidden border-muted">
                      <CardContent className="p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <div className="size-10 rounded-lg bg-accent flex items-center justify-center shrink-0">
                              <Video className="size-4 text-white" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium truncate">{fileName}</p>
                              <p className="text-xs text-muted-foreground">{t('clipLabel', { number: index + 1 })}</p>
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
                                {t('download')}
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
                <div className="text-xs text-muted-foreground mb-1">{t('jobId')}</div>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono">{job.id.substring(0, 16)}...</code>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyJobId}
                    className="p-1 h-6 w-6"
                  >
                    {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
                  </Button>
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">{t('workflow')}</div>
                <Badge variant="outline" className="text-xs">
                  {getWorkflowLabel(job.workflow)}
                </Badge>
              </div>
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">{t('processingTime')}</div>
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="size-3" />
                  {job.duration_seconds ? formatDuration(job.duration_seconds) : formatDurationFromTimestamps(job.created_at)}
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted border">
                <div className="text-xs text-muted-foreground mb-1">{t('stepsCompleted')}</div>
                <div className="text-sm font-medium">
                  {t('stepsCount', { completed: completedSteps, total: totalSteps })}
                </div>
              </div>
              
              {job.duration_seconds && (
                <div className="p-3 rounded-lg bg-muted border">
                  <div className="text-xs text-muted-foreground mb-1">{t('generationTime')}</div>
                  <div className="text-sm font-medium">
                    {formatDuration(job.duration_seconds)}
                  </div>
                  {job.duration_seconds > 300 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {t('complexVideoHint')}
                    </div>
                  )}
                  {job.duration_seconds < 60 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {t('fastGenerationHint')}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Processing Steps Summary */}
          <div className="p-4 rounded-lg bg-muted border">
            <div className="flex items-center gap-3 mb-3">
              <div className="size-6 rounded-full bg-success flex items-center justify-center">
                <CheckCircle className="size-3 text-white" />
              </div>
              <div>
                <div className="font-medium text-sm">
                  {t('allStepsCompleted')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {job.workflow === 'podcastclips' && clipsData.clips_count > 0
                    ? t('clipsReadyForDownload', { count: clipsData.clips_count })
                    : t('videoReadyForDownload')}
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
              {job.workflow === 'podcastclips' ? t('createMoreClips') : t('createAnotherVideo')}
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
                    {t('downloadVideo')}
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
