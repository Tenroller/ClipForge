'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { formatDuration } from '@/lib/formatDuration';
import { cn } from '@/lib/utils';
import {
  ArrowLeft,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  PlayCircle,
  Download,
  ExternalLink,
  RotateCcw,
} from "lucide-react";

function getStatusIcon(status: string) {
  switch (status) {
    case 'queued':
      return <Clock className="size-5 text-muted-foreground" />;
    case 'running':
    case 'processing':
      return <Loader2 className="size-5 animate-spin text-blue-500" />;
    case 'done':
    case 'completed':
      return <CheckCircle2 className="size-5 text-green-500" />;
    case 'error':
      return <XCircle className="size-5 text-red-500" />;
    case 'cancelled':
      return <XCircle className="size-5 text-muted-foreground" />;
    default:
      return <PlayCircle className="size-5 text-muted-foreground" />;
  }
}

function getStatusColor(status: string): 'secondary' | 'default' | 'destructive' | 'outline' {
  switch (status) {
    case 'queued':
      return 'secondary';
    case 'running':
    case 'processing':
      return 'default';
    case 'done':
    case 'completed':
      return 'default'; // Green is handled by class usually, but default is fine
    case 'error':
      return 'destructive';
    case 'cancelled':
      return 'secondary';
    default:
      return 'outline';
  }
}

function getInitialSteps(workflow: string) {
  if (workflow === 'brainrot') {
    return [
      { key: 'download_video', label: 'Download Video' },
      { key: 'extract_audio', label: 'Extract Audio' },
      { key: 'segment_audio', label: 'Segment Audio' },
      { key: 'generate_clips', label: 'Generate Clips' },
      { key: 'compile_videos', label: 'Compile Videos' },
      { key: 'done', label: 'Complete' },
    ];
  } else if (workflow === 'podcastclips') {
    return [
      { key: 'initialization', label: 'Initialize' },
      { key: 'download', label: 'Download Video' },
      { key: 'transcription', label: 'Transcribe Audio' },
      { key: 'speaker_diarization', label: 'Identify Speakers' },
      { key: 'ai_analysis', label: 'AI Analysis' },
      { key: 'scoring', label: 'Score Moments' },
      { key: 'hook_optimization', label: 'Optimize Hooks' },
      { key: 'face_detection', label: 'Detect Faces' },
      { key: 'speaker_detection', label: 'Detect Speakers' },
      { key: 'clip_generation', label: 'Generate Clips' },
      { key: 'finalization', label: 'Finalize' },
      { key: 'post_processing', label: 'Post Processing' },
      { key: 'completed', label: 'Complete' },
    ];
  } else {
    return [
      { key: 'script', label: 'Generate Script' },
      { key: 'voice', label: 'Generate Voice' },
      { key: 'music', label: 'Add Music' },
      { key: 'video', label: 'Generate Video' },
      { key: 'subtitles', label: 'Add Subtitles' },
      { key: 'combine', label: 'Combine Media' },
      { key: 'upload', label: 'Upload' },
      { key: 'done', label: 'Complete' },
    ];
  }
}

function calculateProgress(currentStep?: string, status?: string, workflow?: string) {
  if (status === 'done' || status === 'completed') return 100;
  if (status === 'error' || status === 'cancelled') return 0;
  if (!currentStep) return 0;

  const steps = getInitialSteps(workflow || 'unknown');
  const currentIndex = steps.findIndex((s) => s.key === currentStep);
  return currentIndex >= 0 ? Math.round(((currentIndex + 1) / steps.length) * 100) : 0;
}

export default function JobMonitoringPage() {
  const t = useTranslations('jobMonitor');
  const params = useParams();
  const router = useRouter();
  const jobId = params?.jobId as string;

  const { data: job, isLoading, error } = useJob(jobId, { refetchInterval: 2000 });
  const [autoRefresh, setAutoRefresh] = useState(true);

  const formatJobDuration = () => {
    if (job?.duration_seconds) {
      return formatDuration(job.duration_seconds);
    } else if (job?.started_at) {
      const startTime = new Date(job.started_at).getTime();
      const currentTime = Date.now();
      const durationSeconds = Math.floor((currentTime - startTime) / 1000);
      return formatDuration(durationSeconds);
    }
    return 'N/A';
  };

  const handleViewResult = () => {
    if (job?.output_url) {
      window.open(job.output_url, '_blank');
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-center space-y-4">
          <Loader2 className="size-8 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">Loading job details...</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="container mx-auto py-8">
        <div className="max-w-md mx-auto text-center space-y-6">
          <div className="size-16 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mx-auto">
            <XCircle className="size-8 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">{t('jobNotFound')}</h2>
            <p className="text-muted-foreground mt-2">{t('jobNotFoundDesc')}</p>
          </div>
          <Button onClick={() => router.push('/activity')}>
            <ArrowLeft className="size-4 mr-2" />
            {t('backToActivity')}
          </Button>
        </div>
      </div>
    );
  }

  const steps = getInitialSteps(job.workflow);
  const progress = job.progress ?? calculateProgress(job.current_step, job.status, job.workflow);

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/activity')}
            className="shrink-0"
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              Job Details
              <Badge variant="outline" className="font-mono font-normal text-xs">
                {job.id.substring(0, 8)}
              </Badge>
            </h1>
            <p className="text-muted-foreground text-sm">
              {job.workflow === 'brainrot' ? 'Brainrot Compilation' :
                job.workflow === 'podcastclips' ? 'Podcast Clips' :
                  'AI Video Generation'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={cn(
              "transition-colors",
              autoRefresh && "bg-secondary text-secondary-foreground"
            )}
          >
            <RotateCcw className={cn("size-3.5 mr-2", autoRefresh && "animate-spin")} />
            {autoRefresh ? 'Auto-refresh On' : 'Auto-refresh Off'}
          </Button>

          {(job.status === 'done' || job.status === 'completed') && job.output_url && (
            <>
              <Button onClick={handleViewResult} size="sm">
                <ExternalLink className="size-3.5 mr-2" />
                View Result
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={job.output_url} download target="_blank" rel="noreferrer">
                  <Download className="size-3.5 mr-2" />
                  Download
                </a>
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Status Column */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(job.status)}
                  <span className="text-lg font-medium capitalize">{job.status}</span>
                </div>
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">Duration</div>
                  <div className="font-mono font-medium">{formatJobDuration()}</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-medium">{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>

              {job.error_message && (
                <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
                  <div className="font-semibold mb-1">Error Details</div>
                  {job.error_message}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Workflow Steps</CardTitle>
              <CardDescription>
                Timeline of the processing steps
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative pl-6 border-l-2 border-muted space-y-8 my-2">
                {steps.map((step, index) => {
                  const currentStepIndex = steps.findIndex(s => s.key === job.current_step);
                  const isCompleted =
                    (job.status === 'done' || job.status === 'completed') ||
                    (currentStepIndex >= 0 && index < currentStepIndex);
                  const isCurrent =
                    step.key === job.current_step &&
                    (job.status === 'running' || job.status === 'processing');
                  const isPending = !isCompleted && !isCurrent;

                  return (
                    <div key={step.key} className="relative">
                      {/* Timeline Dot */}
                      <div
                        className={cn(
                          "absolute -left-[31px] top-0 size-4 rounded-full border-2 transition-colors duration-300",
                          isCompleted ? "bg-primary border-primary" :
                            isCurrent ? "bg-background border-primary animate-pulse" :
                              "bg-background border-muted"
                        )}
                      />

                      <div className="space-y-1">
                        <div className={cn(
                          "text-sm font-medium leading-none transition-colors",
                          isCompleted ? "text-foreground" :
                            isCurrent ? "text-primary" :
                              "text-muted-foreground"
                        )}>
                          {step.label}
                        </div>
                        {isCurrent && (
                          <div className="text-xs text-muted-foreground animate-pulse">
                            Processing...
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Info Column */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Job Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">Created</span>
                <span>{job.created_at ? new Date(job.created_at).toLocaleDateString() : '-'}</span>
              </div>
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">Time</span>
                <span>{job.created_at ? new Date(job.created_at).toLocaleTimeString() : '-'}</span>
              </div>
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">Workflow</span>
                <span className="capitalize">{job.workflow}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-muted-foreground">ID</span>
                <span className="font-mono text-xs">{job.id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
