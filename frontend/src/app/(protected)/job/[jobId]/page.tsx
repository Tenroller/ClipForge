'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { formatDuration } from '@/lib/formatDuration';
import {
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  Pause,
  Clock,
  Play,
  Eye,
  Download,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

function getStatusIcon(status: string) {
  switch (status) {
    case 'queued':
      return <Clock className="size-4" />;
    case 'running':
    case 'processing':
      return <Loader2 className="size-4 animate-spin" />;
    case 'done':
    case 'completed':
      return <CheckCircle className="size-4 text-green-600" />;
    case 'error':
      return <XCircle className="size-4 text-red-600" />;
    case 'cancelled':
      return <Pause className="size-4 text-gray-600" />;
    default:
      return <Play className="size-4" />;
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
      return 'default';
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
      { key: 'download_video', label: 'Download Video', done: false },
      { key: 'extract_audio', label: 'Extract Audio', done: false },
      { key: 'segment_audio', label: 'Segment Audio', done: false },
      { key: 'generate_clips', label: 'Generate Clips', done: false },
      { key: 'compile_videos', label: 'Compile Videos', done: false },
      { key: 'done', label: 'Complete', done: false },
    ];
  } else if (workflow === 'podcastclips') {
    return [
      { key: 'initialization', label: 'Initialize', done: false },
      { key: 'download', label: 'Download Video', done: false },
      { key: 'transcription', label: 'Transcribe Audio', done: false },
      { key: 'speaker_diarization', label: 'Identify Speakers', done: false },
      { key: 'ai_analysis', label: 'AI Analysis', done: false },
      { key: 'scoring', label: 'Score Moments', done: false },
      { key: 'hook_optimization', label: 'Optimize Hooks', done: false },
      { key: 'face_detection', label: 'Detect Faces', done: false },
      { key: 'speaker_detection', label: 'Detect Speakers', done: false },
      { key: 'clip_generation', label: 'Generate Clips', done: false },
      { key: 'finalization', label: 'Finalize', done: false },
      { key: 'post_processing', label: 'Post Processing', done: false },
      { key: 'completed', label: 'Complete', done: false },
    ];
  } else {
    return [
      { key: 'script', label: 'Generate Script', done: false },
      { key: 'voice', label: 'Generate Voice', done: false },
      { key: 'music', label: 'Add Music', done: false },
      { key: 'video', label: 'Generate Video', done: false },
      { key: 'subtitles', label: 'Add Subtitles', done: false },
      { key: 'combine', label: 'Combine Media', done: false },
      { key: 'upload', label: 'Upload', done: false },
      { key: 'done', label: 'Complete', done: false },
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
  const { toast } = useToast();
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="text-center">
            <Loader2 className="size-8 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">Loading job details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
        <div className="text-center py-12">
          <XCircle className="size-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">{t('jobNotFound')}</h2>
          <p className="text-muted-foreground mb-6">
            {t('jobNotFoundDesc')}
          </p>
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push('/activity')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="size-4" />
            Back to Activity
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{t('jobMonitor')}</h1>
            <p className="text-sm text-muted-foreground">
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
            className={autoRefresh ? 'bg-green-50 border-green-200 dark:bg-green-900/20' : ''}
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </Button>

          {(job.status === 'done' || job.status === 'completed') && job.output_url && (
            <>
              <Button onClick={handleViewResult} className="flex items-center gap-2">
                <Eye className="size-4" />
                View Result
              </Button>
              <Button asChild variant="outline">
                <a href={job.output_url} download target="_blank" rel="noreferrer">
                  <Download className="size-4 mr-2" />
                  Download
                </a>
              </Button>
            </>
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
              <Badge variant={getStatusColor(job.status)}>{job.status}</Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Workflow:</span>
              <Badge variant="outline">
                {job.workflow === 'brainrot' ? 'Brainrot Compilation' :
                 job.workflow === 'podcastclips' ? 'Podcast Clips' :
                 'AI Video Generation'}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Duration:</span>
              <span className="text-sm font-mono">{formatJobDuration()}</span>
            </div>

            {job.current_step && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Current Step:</span>
                <span className="text-sm font-medium">{job.current_step.replace(/_/g, ' ')}</span>
              </div>
            )}

            <Separator />

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{t('progress')}</span>
                <span className="font-medium">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>

            {job.error_message && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-950/20 dark:border-red-800/30">
                <p className="text-sm text-red-700 dark:text-red-300">
                  <strong>Error:</strong> {job.error_message}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Steps Progress Card */}
        <Card>
          <CardHeader>
            <CardTitle>{t('processingSteps')}</CardTitle>
            <CardDescription>
              Step-by-step progress through the {job.workflow} workflow
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {steps.map((step, index) => {
                const currentStepIndex = steps.findIndex(s => s.key === job.current_step);
                const isActive =
                  step.key === job.current_step &&
                  (job.status === 'running' || job.status === 'processing');
                const isDone =
                  (job.status === 'done' || job.status === 'completed') ||
                  (currentStepIndex >= 0 && index < currentStepIndex);

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
                    <div
                      className={`size-6 rounded-full border-2 flex items-center justify-center ${
                        isDone
                          ? 'bg-green-500 border-green-500 text-white'
                          : isActive
                          ? 'bg-blue-500 border-blue-500 text-white'
                          : 'border-muted-foreground/30 bg-background'
                      }`}
                    >
                      {isDone ? (
                        <CheckCircle className="size-3" />
                      ) : isActive ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <span className="text-xs font-medium">{index + 1}</span>
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-sm">{step.label}</div>
                      {isActive && (
                        <div className="text-xs text-blue-600 dark:text-blue-400">Processing...</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
