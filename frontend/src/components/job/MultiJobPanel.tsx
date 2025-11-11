'use client';

import { useState } from 'react';
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

function getWorkflowLabel(workflow: string): string {
  switch (workflow) {
    case 'moneyprinter':
      return 'AI Video';
    case 'brainrot':
      return 'Compilation';
    default:
      return workflow;
  }
}

export function MultiJobPanel({ jobs, onViewResult, onRemoveJob, onClearCompleted }: MultiJobPanelProps) {
  const [showCompleted, setShowCompleted] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  const activeJobs = jobs.filter((job) => !['done', 'completed', 'error', 'cancelled'].includes(job.status));
  const completedJobs = jobs.filter((job) => ['done', 'completed', 'error', 'cancelled'].includes(job.status));
  const hasCompleted = completedJobs.length > 0;

  const visibleJobs = showCompleted ? jobs : activeJobs;

  if (jobs.length === 0) {
    return null;
  }

  return (
    <Card className="enhanced-card border-l-4 border-l-blue-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Loader2 className={`size-4 text-white ${activeJobs.length > 0 ? 'animate-spin' : ''}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span>Job Queue</span>
                <Badge variant="outline" className="text-xs">
                  {activeJobs.length} active
                </Badge>
                {hasCompleted && (
                  <Badge variant="secondary" className="text-xs">
                    {completedJobs.length} completed
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
                  {showCompleted ? 'Hide' : 'Show'} Completed
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClearCompleted}
                  className="text-xs h-7 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-3 mr-1" />
                  Clear
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
                {showCompleted ? 'No completed jobs' : 'No active jobs'}
              </div>
            ) : (
              visibleJobs.map((job) => (
                <div
                  key={job.id}
                  className={`relative p-4 rounded-lg border transition-all duration-200 ${
                    job.status === 'done' || job.status === 'completed'
                      ? 'bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800/30'
                      : job.status === 'error'
                      ? 'bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800/30'
                      : job.status === 'cancelled'
                      ? 'bg-gray-50 border-gray-200 dark:bg-gray-950/20 dark:border-gray-800/30'
                      : 'bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800/30'
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
                          className={`size-6 rounded-full border-2 flex items-center justify-center ${
                            job.status === 'done' || job.status === 'completed'
                              ? 'bg-green-500 border-green-500 text-white'
                              : job.status === 'error'
                              ? 'bg-red-500 border-red-500 text-white'
                              : job.status === 'cancelled'
                              ? 'bg-gray-500 border-gray-500 text-white'
                              : 'bg-blue-500 border-blue-500 text-white'
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
                            Job {job.id.substring(0, 8)}...
                            {job.duration_seconds && (
                              <span className="ml-2 text-blue-600 dark:text-blue-400">
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
                            See Result
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {!['done', 'completed', 'error', 'cancelled'].includes(job.status) && job.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">
                            {job.current_step ? `Step: ${job.current_step.replace(/_/g, ' ')}` : 'Initializing...'}
                          </span>
                          <span className="font-medium">{job.progress}%</span>
                        </div>
                        <Progress value={job.progress} className="h-2" />
                      </div>
                    )}

                    {/* Error Message */}
                    {job.status === 'error' && job.error_message && (
                      <div className="text-xs text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/20 p-2 rounded">
                        Error: {job.error_message}
                      </div>
                    )}

                    {/* Current Step for Active Jobs */}
                    {(job.status === 'running' || job.status === 'processing') && job.current_step && (
                      <div className="text-xs text-muted-foreground">
                        Processing: {job.current_step.replace(/_/g, ' ')}
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
