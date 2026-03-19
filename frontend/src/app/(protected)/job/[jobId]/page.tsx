'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
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

import { getStatusIconColor } from '@/lib/status';

function getStatusIcon(status: string) {
  switch (status) {
    case 'queued':
      return <Clock className={`size-5 ${getStatusIconColor('queued')}`} />;
    case 'running':
    case 'processing':
      return <Loader2 className={`size-5 animate-spin ${getStatusIconColor('running')}`} />;
    case 'done':
    case 'completed':
      return <CheckCircle2 className={`size-5 ${getStatusIconColor('done')}`} />;
    case 'error':
      return <XCircle className={`size-5 ${getStatusIconColor('error')}`} />;
    case 'cancelled':
      return <XCircle className="size-5 text-muted-foreground" />;
    default:
      return <PlayCircle className="size-5 text-muted-foreground" />;
  }
}

function getInitialSteps(workflow: string, t: (key: string) => string) {
  if (workflow === 'brainrot') {
    return [
      { key: 'download_video', label: t('steps.downloadVideo') },
      { key: 'extract_audio', label: t('steps.extractAudio') },
      { key: 'segment_audio', label: t('steps.segmentAudio') },
      { key: 'generate_clips', label: t('steps.generateClips') },
      { key: 'compile_videos', label: t('steps.compileVideos') },
      { key: 'done', label: t('steps.done') },
    ];
  } else if (workflow === 'podcastclips') {
    return [
      { key: 'initialization', label: t('steps.initialization') },
      { key: 'download', label: t('steps.download') },
      { key: 'transcription', label: t('steps.transcription') },
      { key: 'speaker_diarization', label: t('steps.speakerDiarization') },
      { key: 'ai_analysis', label: t('steps.aiAnalysis') },
      { key: 'scoring', label: t('steps.scoring') },
      { key: 'hook_optimization', label: t('steps.hookOptimization') },
      { key: 'face_detection', label: t('steps.faceDetection') },
      { key: 'speaker_detection', label: t('steps.speakerDetection') },
      { key: 'clip_generation', label: t('steps.clipGeneration') },
      { key: 'finalization', label: t('steps.finalization') },
      { key: 'post_processing', label: t('steps.postProcessing') },
      { key: 'completed', label: t('steps.completed') },
    ];
  } else {
    return [
      { key: 'script', label: t('steps.script') },
      { key: 'voice', label: t('steps.voice') },
      { key: 'music', label: t('steps.music') },
      { key: 'video', label: t('steps.video') },
      { key: 'subtitles', label: t('steps.subtitles') },
      { key: 'combine', label: t('steps.combine') },
      { key: 'upload', label: t('steps.upload') },
      { key: 'done', label: t('steps.done') },
    ];
  }
}

function calculateProgress(currentStep?: string, status?: string, workflow?: string, t?: (key: string) => string) {
  if (status === 'done' || status === 'completed') return 100;
  if (status === 'error' || status === 'cancelled') return 0;
  if (!currentStep) return 0;

  const steps = getInitialSteps(workflow || 'unknown', t!);
  const currentIndex = steps.findIndex((s) => s.key === currentStep);
  return currentIndex >= 0 ? Math.round(((currentIndex + 1) / steps.length) * 100) : 0;
}

export default function JobMonitoringPage() {
  const t = useTranslations('jobMonitor');
  const params = useParams();
  const router = useRouter();
  const jobId = params?.jobId as string;
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [now, setNow] = useState(() => Date.now());

  // Update current time for live duration display
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const { data: job, isLoading, error } = useJob(jobId, {
    refetchInterval: autoRefresh ? 3000 : false  // 3 seconds when enabled, disabled when off
  });

  const formatJobDuration = () => {
    if (job?.duration_seconds) {
      return formatDuration(job.duration_seconds);
    } else if (job?.started_at) {
      const startTime = new Date(job.started_at).getTime();
      const durationSeconds = Math.floor((now - startTime) / 1000);
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
          <p className="text-muted-foreground">{t('loadingJobDetails')}</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="container mx-auto py-8">
        <div className="max-w-md mx-auto text-center space-y-6">
          <div className="size-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
            <XCircle className="size-8 text-destructive" />
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

  const steps = getInitialSteps(job.workflow, t);
  const progress = job.progress ?? calculateProgress(job.current_step, job.status, job.workflow, t);

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
            aria-label={t('back') || 'Back'}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              {t('jobDetails')}
              <Badge variant="outline" className="font-mono font-normal text-xs">
                {job.id.substring(0, 8)}
              </Badge>
            </h1>
            <p className="text-muted-foreground text-sm">
              {job.workflow === 'brainrot' ? t('brainrotCompilation') :
                job.workflow === 'podcastclips' ? t('podcastClips') :
                  t('aiVideoGeneration')}
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
            {autoRefresh ? t('autoRefreshOn') : t('autoRefreshOff')}
          </Button>

          {(job.status === 'done' || job.status === 'completed') && job.output_url && (
            <>
              <Button onClick={handleViewResult} size="sm">
                <ExternalLink className="size-3.5 mr-2" />
                {t('viewResult')}
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={job.output_url} download target="_blank" rel="noreferrer">
                  <Download className="size-3.5 mr-2" />
                  {t('download')}
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
              <CardTitle>{t('status')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(job.status)}
                  <span className="text-lg font-medium capitalize">{job.status}</span>
                </div>
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">{t('duration')}</div>
                  <div className="font-mono font-medium">{formatJobDuration()}</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t('progress')}</span>
                  <span className="font-medium">{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>

              {job.error_message && (
                <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
                  <div className="font-semibold mb-1">{t('errorDetails')}</div>
                  {job.error_message}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('workflowSteps')}</CardTitle>
              <CardDescription>
                {t('timelineOfSteps')}
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
                          <div className="text-xs text-muted-foreground">
                            {t('processing')}
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
              <CardTitle className="text-base">{t('jobInformation')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">{t('created')}</span>
                <span>{job.created_at ? new Date(job.created_at).toLocaleDateString() : '-'}</span>
              </div>
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">{t('time')}</span>
                <span>{job.created_at ? new Date(job.created_at).toLocaleTimeString() : '-'}</span>
              </div>
              <div className="flex justify-between py-2 border-b">
                <span className="text-muted-foreground">{t('workflow')}</span>
                <span className="capitalize">{job.workflow}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-muted-foreground">{t('id')}</span>
                <span className="font-mono text-xs">{job.id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
