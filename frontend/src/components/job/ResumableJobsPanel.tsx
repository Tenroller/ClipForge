'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { RotateCw, RefreshCw, Play, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { useResumableJobs, useResumeJob } from '@/hooks/use-jobs';
import type { JobRecord } from '@/lib/api';

interface ResumableJobsPanelProps {
  onJobResumed?: (jobId: string) => void;
}

export default function ResumableJobsPanel({ onJobResumed }: ResumableJobsPanelProps) {
  const { toast } = useToast();
  const t = useTranslations('common');
  const router = useRouter();
  const { data: resumableJobs = [], isLoading, refetch } = useResumableJobs();
  const resumeJobMutation = useResumeJob();
  const [resumingJobs, setResumingJobs] = useState<Set<string>>(new Set());

  const handleResumeJob = async (jobId: string) => {
    setResumingJobs((prev) => new Set(prev).add(jobId));

    try {
      const result = await resumeJobMutation.mutateAsync(jobId);

      toast({
        title: 'Job Resumed',
        description: `New job ID: ${result.job_id.substring(0, 8)}...`,
      });

      // Navigate to the new job
      router.push(`/job/${result.job_id}`);

      onJobResumed?.(result.job_id);

      // Refresh the resumable jobs list
      refetch();
    } catch (error: any) {
      toast({
        title: 'Failed to Resume Job',
        description: error.message || 'Please try again or create a new job',
        variant: 'destructive',
      });
    } finally {
      setResumingJobs((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'error':
        return <AlertTriangle className="size-4 text-red-500" />;
      case 'cancelled':
        return <Clock className="size-4 text-orange-500" />;
      default:
        return <CheckCircle className="size-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'error':
        return <Badge variant="destructive">Failed</Badge>;
      case 'cancelled':
        return <Badge variant="secondary">Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const getWorkflowName = (workflow: string) => {
    switch (workflow) {
      case 'moneyprinter':
        return 'ClipForge AI Creator';
      case 'brainrot':
        return 'Brainrot Compilation';
      default:
        return workflow;
    }
  };

  if (isLoading && resumableJobs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="size-5 animate-spin" />
            {t('loadingResumableJobs')}
          </CardTitle>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Resume Interrupted Jobs</h3>
          <p className="text-sm text-muted-foreground">Restart video generation from where it was interrupted</p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`size-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {resumableJobs.length === 0 ? (
        <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg dark:bg-green-950/20 dark:border-green-800/30">
          <CheckCircle className="size-4 text-green-600" />
          <span className="text-green-800 dark:text-green-200">
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
                      <CardTitle className="text-base">{getWorkflowName(job.workflow)}</CardTitle>
                      <CardDescription className="text-sm">Job ID: {job.id.slice(0, 8)}...</CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(job.status)}
                    <Button
                      size="sm"
                      onClick={() => handleResumeJob(job.id)}
                      disabled={resumingJobs.has(job.id)}
                      title="Resume this job from where it left off"
                    >
                      {resumingJobs.has(job.id) ? (
                        <RefreshCw className="size-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="size-4 mr-2" />
                      )}
                      Resume
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="pt-0">
                <div className="space-y-2">
                  {job.current_step && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Last step:</span>
                        <br />
                        <span className="text-muted-foreground">{job.current_step.replace(/_/g, ' ')}</span>
                      </div>
                      <div>
                        <span className="font-medium">Progress:</span>
                        <br />
                        <span className="text-muted-foreground">{job.progress || 0}%</span>
                      </div>
                      <div>
                        <span className="font-medium">Status:</span>
                        <br />
                        <span className="text-muted-foreground">{job.status}</span>
                      </div>
                    </div>
                  )}

                  {job.error_message && (
                    <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-950/20 dark:border-red-800/30">
                      <AlertTriangle className="size-4 text-red-600" />
                      <div className="text-red-800 dark:text-red-200 text-sm">
                        <strong>Error:</strong> {job.error_message}
                      </div>
                    </div>
                  )}

                  <div className="text-xs text-muted-foreground">
                    Last updated: {job.created_at ? formatDate(job.created_at) : 'N/A'}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
