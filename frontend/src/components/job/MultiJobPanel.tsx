'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Loader2,
  ChevronDown,
  ChevronUp,
  Eye,
  X,
  Trash2,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  Pause,
} from "lucide-react";
import type { JobRecord } from '@/lib/api';
import { formatDuration } from '@/lib/formatDuration';
import { getStatusDotColor, getFeedbackClasses } from '@/lib/status';

interface MultiJobPanelProps {
  jobs: JobRecord[];
  onViewResult: (job: JobRecord) => void;
  onRemoveJob: (jobId: string) => void;
  onClearCompleted: () => void;
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'queued':
      return <Clock className="size-3" />;
    case 'running':
    case 'processing':
      return <Loader2 className="size-3 animate-spin" />;
    case 'done':
    case 'completed':
      return <CheckCircle className="size-3" />;
    case 'error':
      return <XCircle className="size-3" />;
    case 'cancelled':
      return <Pause className="size-3" />;
    default:
      return <Play className="size-3" />;
  }
}

function getStatusColor(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'done':
    case 'completed':
      return 'default';
    case 'error':
      return 'destructive';
    case 'cancelled':
      return 'secondary';
    case 'running':
    case 'processing':
      return 'default';
    default:
      return 'outline';
  }
}

export function MultiJobPanel({ jobs, onViewResult, onRemoveJob, onClearCompleted }: MultiJobPanelProps) {
  const [showCompleted, setShowCompleted] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const t = useTranslations('multiJobPanel');

  const getWorkflowLabel = (workflow: string): string => {
    switch (workflow) {
      case 'moneyprinter':
        return t('workflowAiVideo');
      case 'brainrot':
        return t('workflowCompilation');
      case 'podcastclips':
        return t('workflowPodcastClips');
      default:
        return workflow;
    }
  };

  const activeJobs = jobs.filter((job) => !['done', 'completed', 'error', 'cancelled'].includes(job.status));
  const completedJobs = jobs.filter((job) => ['done', 'completed', 'error', 'cancelled'].includes(job.status));
  const hasCompleted = completedJobs.length > 0;

  const visibleJobs = showCompleted ? jobs : activeJobs;

  if (jobs.length === 0) {
    return null;
  }

  return (
    <Card className="enhanced-card border-l-4 border-l-info">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-br from-info to-accent flex items-center justify-center">
              <Loader2 className={`size-4 text-white ${activeJobs.length > 0 ? 'animate-spin' : ''}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span>{t('jobQueue')}</span>
                <Badge variant="outline" className="text-xs">
                  {t('active', { count: activeJobs.length })}
                </Badge>
                {hasCompleted && (
                  <Badge variant="secondary" className="text-xs">
                    {t('completed', { count: completedJobs.length })}
                  </Badge>
                )}
              </div>
            </div>
          </CardTitle>

          <div className="flex items-center gap-2">
            {hasCompleted && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowCompleted(!showCompleted)}
                  className="text-xs h-7"
                >
                  {showCompleted ? t('hideCompleted') : t('showCompleted')}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClearCompleted}
                  className="text-xs h-7 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-3 mr-1" />
                  {t('clear')}
                </Button>
              </>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 h-7 w-7"
            >
              {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-3">
            {visibleJobs.length === 0 ? (
              <div className="text-center py-4 text-sm text-muted-foreground">
                {showCompleted ? t('noCompletedJobs') : t('noActiveJobs')}
              </div>
            ) : (
              visibleJobs.map((job) => (
                <div
                  key={job.id}
                  className={`relative p-4 rounded-lg border transition-all duration-200 ${
                    job.status === 'done' || job.status === 'completed'
                      ? getFeedbackClasses('success').card
                      : job.status === 'error'
                      ? getFeedbackClasses('error').card
                      : job.status === 'cancelled'
                      ? 'bg-muted border-border'
                      : getFeedbackClasses('info').card
                  }`}
                >
                  {/* Remove button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemoveJob(job.id)}
                    className="absolute top-2 right-2 p-1 h-6 w-6 opacity-60 hover:opacity-100 text-muted-foreground hover:text-destructive"
                  >
                    <X className="size-3" />
                  </Button>

                  <div className="space-y-3 pr-8">
                    {/* Job Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`size-6 rounded-full border-2 flex items-center justify-center text-white ${
                            job.status === 'done' || job.status === 'completed'
                              ? `${getStatusDotColor('done')} border-success`
                              : job.status === 'error'
                              ? `${getStatusDotColor('error')} border-destructive`
                              : job.status === 'cancelled'
                              ? `${getStatusDotColor('cancelled')} border-muted-foreground`
                              : `${getStatusDotColor('running')} border-info`
                          }`}
                        >
                          {getStatusIcon(job.status)}
                        </div>

                        <div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] uppercase font-medium">
                              {getWorkflowLabel(job.workflow)}
                            </Badge>
                            <Badge variant={getStatusColor(job.status)} className="text-xs">
                              {job.status}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {t('jobId', { id: job.id.substring(0, 8) })}
                            {job.duration_seconds && (
                              <span className="ml-2 text-info">
                                • {formatDuration(job.duration_seconds)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        {(job.status === 'done' || job.status === 'completed') && job.output_url && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => onViewResult(job)}
                            className="h-8 px-3 text-xs"
                          >
                            <Eye className="size-3 mr-1" />
                            {t('seeResult')}
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {!['done', 'completed', 'error', 'cancelled'].includes(job.status) && job.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">
                            {job.current_step ? t('step', { step: job.current_step.replace(/_/g, ' ') }) : t('initializing')}
                          </span>
                          <span className="font-medium">{job.progress}%</span>
                        </div>
                        <Progress value={job.progress} className="h-2" />
                      </div>
                    )}

                    {/* Error Message */}
                    {job.status === 'error' && job.error_message && (
                      <div className="text-xs text-destructive bg-destructive/10 p-2 rounded">
                        {t('errorPrefix', { message: job.error_message })}
                      </div>
                    )}

                    {/* Current Step for Active Jobs */}
                    {(job.status === 'running' || job.status === 'processing') && job.current_step && (
                      <div className="text-xs text-muted-foreground">
                        {t('processing', { step: job.current_step.replace(/_/g, ' ') })}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
