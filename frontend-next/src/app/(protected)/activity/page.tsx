'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useJobs, useRemakeJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import ResultPanel from '@/components/job/ResultPanel';
import { FaEye, FaRedo, FaSpinner, FaChartLine, FaDownload } from 'react-icons/fa';
import type { JobRecord } from '@/lib/api';

export default function ActivityPage() {
  const router = useRouter();
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
        title: 'Job Remade Successfully',
        description: `New job ID: ${result.job_id.substring(0, 8)}...`,
      });

      // Refresh jobs list
      refetch();
    } catch (error: any) {
      toast({
        title: 'Failed to Remake Job',
        description: error.message || 'Unknown error',
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
    return ['completed', 'done', 'error', 'cancelled'].includes(job.status) && job.request_data;
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
        return 'AI Video';
      case 'brainrot':
        return 'Compilation';
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
      <div className="container-page fade-in max-w-[1200px]">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    );
  }

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Job Activity</h1>
            <p className="text-muted-foreground mt-2">View and manage your video generation jobs</p>
          </div>
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <FaRedo className={`size-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Jobs List */}
        <Card className="enhanced-card">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Recent Jobs</span>
              <Badge variant="outline">{jobs.length} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading && jobs.length === 0 ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <FaSpinner className="size-5 mr-2 animate-spin" />
                Loading jobs...
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No jobs found</p>
                <p className="text-sm mt-2">Create your first video to see it here</p>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
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
                          Step: {job.current_step}
                        </div>
                      )}

                      {job.progress !== undefined && job.progress >= 0 && job.status !== 'completed' && job.status !== 'done' && (
                        <div className="mb-2">
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground">Progress</span>
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
                        {job.created_at && `Created: ${formatDate(job.created_at)}`}
                        {job.duration_seconds && ` • Duration: ${Math.floor(job.duration_seconds / 60)}m ${job.duration_seconds % 60}s`}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      {/* Monitor button for all jobs */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push(`/job/${job.id}`)}
                        className="h-8 px-3 text-xs"
                        title="Monitor job progress"
                      >
                        <FaChartLine className="size-3 mr-1" />
                        Monitor
                      </Button>

                      {/* View button for completed jobs with output */}
                      {(job.status === 'completed' || job.status === 'done') && job.output_url && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleViewResult(job)}
                          className="h-8 px-3 text-xs"
                        >
                          <FaEye className="size-3 mr-1" />
                          View
                        </Button>
                      )}

                      {/* Download button for completed jobs */}
                      {(job.status === 'completed' || job.status === 'done') && job.output_url && (
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
                            <FaDownload className="size-3 mr-1" />
                            Download
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
                          title="Remake with same parameters"
                        >
                          {remakingJobs.has(job.id) ? (
                            <FaSpinner className="size-3 mr-1 animate-spin" />
                          ) : (
                            <FaRedo className="size-3 mr-1" />
                          )}
                          Remake
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Stats Card */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {jobs.filter(j => j.status === 'completed' || j.status === 'done').length}
              </div>
              <p className="text-xs text-muted-foreground">Completed</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {jobs.filter(j => ['processing', 'running', 'queued'].includes(j.status)).length}
              </div>
              <p className="text-xs text-muted-foreground">In Progress</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {jobs.filter(j => j.status === 'error').length}
              </div>
              <p className="text-xs text-muted-foreground">Failed</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {jobs.filter(j => j.status === 'cancelled').length}
              </div>
              <p className="text-xs text-muted-foreground">Cancelled</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
