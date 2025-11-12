'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useJobs, useRemakeJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import ResultPanel from '@/components/job/ResultPanel';
import { Download, Eye, Loader2, RefreshCw, TrendingUp } from "lucide-react";
import type { JobRecord } from '@/lib/api';

export default function ActivityPage() {
  const router = useRouter();
  const t = useTranslations('activity');
  const { toast } = useToast();
  const { data: jobs = [], isLoading, refetch } = useJobs({ limit: 50, refetchInterval: 5000 });
  const remakeJobMutation = useRemakeJob();

  const [selectedResult, setSelectedResult] = useState<JobRecord | null>(null);
  const [remakingJobs, setRemakingJobs] = useState<Set<string>>(new Set());

  const handleViewResult = (job: JobRecord) => {
    setSelectedResult(job);
  };

  const handleCloseResult = () => {
    setSelectedResult(null);
  };

  const handleRemakeJob = async (jobId: string) => {
    try {
      setRemakingJobs(prev => new Set(prev.add(jobId)));
      const result = await remakeJobMutation.mutateAsync(jobId);

      toast({
        title: t('jobRemadeSuccess'),
        description: t('newJobId', { id: result.job_id.substring(0, 8) }),
      });

      // Refresh jobs list
      refetch();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toast({
        title: t('failedToRemake'),
        description: message,
        variant: 'destructive',
      });
    } finally {
      setRemakingJobs(prev => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    }
  };

  const canRemakeJob = (job: JobRecord) => {
    // Can remake jobs that are completed, error, or cancelled and have request_data
    return ['completed', 'done', 'error', 'cancelled'].includes(job.status) && !!job.request_data;
  };

  const getStatusVariant = (status: string): 'default' | 'destructive' | 'secondary' | 'outline' => {
    switch (status) {
      case 'completed':
      case 'done':
        return 'default';
      case 'error':
        return 'destructive';
      case 'processing':
      case 'running':
      case 'queued':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getWorkflowLabel = (workflow: string) => {
    switch (workflow) {
      case 'moneyprinter':
        return t('workflows.aiVideo');
      case 'brainrot':
        return t('workflows.compilation');
      default:
        return workflow;
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'N/A';
    }
  };

  // If showing results, render the result panel
  if (selectedResult) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
      <div className="space-y-6">
        {/* Enhanced Header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <div className="inline-block">
              <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                {t('title')}
              </h1>
              <div className="h-1 w-24 bg-gradient-to-r from-primary to-accent rounded-full mt-2" />
            </div>
            <p className="text-base text-muted-foreground max-w-2xl">
              {t('description')}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`size-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            {t('refresh')}
          </Button>
        </div>

        {/* Jobs List */}
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardHeader className="border-b bg-gradient-to-r from-muted/30 to-muted/10">
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                  <TrendingUp className="size-5 text-white" />
                </div>
                <span className="text-xl">{t('recentJobs')}</span>
              </div>
              <Badge variant="outline" className="px-3 py-1 text-sm">
                {jobs.length} {t('total')}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {isLoading && jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <Loader2 className="size-12 mb-4 animate-spin text-primary" />
                <p className="text-lg font-medium">{t('loadingJobs')}</p>
                <p className="text-sm mt-2">{t('loadingMessage')}</p>
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-16">
                <div className="size-20 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
                  <TrendingUp className="size-10 text-muted-foreground" />
                </div>
                <p className="text-xl font-semibold text-foreground mb-2">{t('noJobs')}</p>
                <p className="text-sm text-muted-foreground mb-6">{t('noJobsMessage')}</p>
                <Button asChild className="btn-primary">
                  <a href="/creator">{t('createFirstVideo')}</a>
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job, idx) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-4 rounded-xl border bg-card/50 backdrop-blur-sm hover:bg-accent/10 hover:border-primary/30 transition-all duration-200 hover:shadow-md group"
                    style={{ animationDelay: `${idx * 50}ms` }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <Badge variant="outline" className="text-[10px] uppercase">
                          {getWorkflowLabel(job.workflow)}
                        </Badge>
                        <code className="text-xs font-mono text-muted-foreground">
                          {job.id.substring(0, 16)}...
                        </code>
                        <Badge variant={getStatusVariant(job.status)}>
                          {job.status}
                        </Badge>
                      </div>

                      {job.current_step && (
                        <div className="text-sm text-muted-foreground mb-1">
                          {t('step')}: {job.current_step}
                        </div>
                      )}

                      {job.progress !== undefined && job.progress >= 0 && job.status !== 'completed' && job.status !== 'done' && (
                        <div className="mb-2">
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground">{t('progress')}</span>
                            <span className="font-medium">{job.progress}%</span>
                          </div>
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                        </div>
                      )}

                      <div className="text-xs text-muted-foreground">
                        {job.created_at && `${t('created')}: ${formatDate(job.created_at)}`}
                        {job.duration_seconds && ` • ${t('duration')}: ${Math.floor(job.duration_seconds / 60)}m ${job.duration_seconds % 60}s`}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      {/* Monitor button for all jobs */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push(`/job/${job.id}`)}
                        className="h-8 px-3 text-xs"
                        title={t('monitorProgress')}
                      >
                        <TrendingUp className="size-3 mr-1" />
                        {t('monitor')}
                      </Button>

                      {/* View button for completed jobs with output */}
                      {(job.status === 'completed' || job.status === 'done') && typeof job.output_url === 'string' && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleViewResult(job)}
                          className="h-8 px-3 text-xs"
                        >
                          <Eye className="size-3 mr-1" />
                          {t('view')}
                        </Button>
                      )}

                      {/* Download button for completed jobs */}
                      {(job.status === 'completed' || job.status === 'done') && typeof job.output_url === 'string' && (
                        <Button
                          variant="outline"
                          size="sm"
                          asChild
                          className="h-8 px-3 text-xs"
                        >
                          <a
                            href={job.output_url}
                            download
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Download className="size-3 mr-1" />
                            {t('download')}
                          </a>
                        </Button>
                      )}

                      {/* Remake button for finished jobs */}
                      {canRemakeJob(job) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemakeJob(job.id)}
                          disabled={remakingJobs.has(job.id)}
                          className="h-8 px-3 text-xs"
                          title={t('remakeWith')}
                        >
                          {remakingJobs.has(job.id) ? (
                            <Loader2 className="size-3 mr-1 animate-spin" />
                          ) : (
                            <RefreshCw className="size-3 mr-1" />
                          )}
                          {t('remake')}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Enhanced Stats Card */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="size-10 rounded-lg bg-green-500/10 flex items-center justify-center group-hover:bg-green-500/20 transition-colors">
                  <svg className="size-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="text-3xl font-bold bg-gradient-to-r from-green-500 to-emerald-500 bg-clip-text text-transparent">
                {jobs.filter(j => j.status === 'completed' || j.status === 'done').length}
              </div>
              <p className="text-sm text-muted-foreground font-medium mt-1">{t('stats.completed')}</p>
            </CardContent>
          </Card>
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="size-10 rounded-lg bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
                  <Loader2 className="size-5 text-blue-500" />
                </div>
              </div>
              <div className="text-3xl font-bold bg-gradient-to-r from-blue-500 to-purple-500 bg-clip-text text-transparent">
                {jobs.filter(j => ['processing', 'running', 'queued'].includes(j.status)).length}
              </div>
              <p className="text-sm text-muted-foreground font-medium mt-1">{t('stats.inProgress')}</p>
            </CardContent>
          </Card>
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="size-10 rounded-lg bg-red-500/10 flex items-center justify-center group-hover:bg-red-500/20 transition-colors">
                  <svg className="size-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="text-3xl font-bold text-red-500">
                {jobs.filter(j => j.status === 'error').length}
              </div>
              <p className="text-sm text-muted-foreground font-medium mt-1">{t('stats.failed')}</p>
            </CardContent>
          </Card>
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="size-10 rounded-lg bg-gray-500/10 flex items-center justify-center group-hover:bg-gray-500/20 transition-colors">
                  <svg className="size-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="text-3xl font-bold text-gray-500">
                {jobs.filter(j => j.status === 'cancelled').length}
              </div>
              <p className="text-sm text-muted-foreground font-medium mt-1">{t('stats.cancelled')}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
