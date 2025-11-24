'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useJobs, useRemakeJob } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from '@/hooks/use-toast';
import ResultPanel from '@/components/job/ResultPanel';
import { Download, Eye, Loader2, RefreshCw, TrendingUp, MoreHorizontal, PlayCircle } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
      <div className="container mx-auto py-8 animate-fade-in-up">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground mt-2">
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

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.completed')}
            </CardTitle>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              className="h-4 w-4 text-muted-foreground"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobs.filter(j => j.status === 'completed' || j.status === 'done').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.inProgress')}
            </CardTitle>
            <Loader2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobs.filter(j => ['processing', 'running', 'queued'].includes(j.status)).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.failed')}
            </CardTitle>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              className="h-4 w-4 text-muted-foreground"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" x2="12" y1="8" y2="12" />
              <line x1="12" x2="12.01" y1="16" y2="16" />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobs.filter(j => j.status === 'error').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.cancelled')}
            </CardTitle>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              className="h-4 w-4 text-muted-foreground"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="15" x2="9" y1="9" y2="15" />
              <line x1="9" x2="15" y1="9" y2="15" />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobs.filter(j => j.status === 'cancelled').length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Jobs Table */}
      <Card>
        <CardHeader>
          <CardTitle>{t('recentJobs')}</CardTitle>
          <CardDescription>
            A list of your recent video generation jobs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="size-8 mb-4 animate-spin" />
              <p>{t('loadingJobs')}</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>{t('noJobs')}</p>
              <Button asChild className="mt-4" variant="outline">
                <a href="/creator">{t('createFirstVideo')}</a>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">ID</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Step</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-xs">
                      {job.id.substring(0, 8)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal">
                        {getWorkflowLabel(job.workflow || '')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusVariant(job.status)}>
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {job.current_step || '-'}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatDate(job.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" className="h-8 w-8 p-0">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          <DropdownMenuItem onClick={() => router.push(`/job/${job.id}`)}>
                            <TrendingUp className="mr-2 h-4 w-4" />
                            {t('monitor')}
                          </DropdownMenuItem>
                          {(job.status === 'completed' || job.status === 'done') && typeof job.output_url === 'string' && (
                            <>
                              <DropdownMenuItem onClick={() => handleViewResult(job)}>
                                <Eye className="mr-2 h-4 w-4" />
                                {t('view')}
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <a href={job.output_url} download target="_blank" rel="noreferrer">
                                  <Download className="mr-2 h-4 w-4" />
                                  {t('download')}
                                </a>
                              </DropdownMenuItem>
                            </>
                          )}
                          {canRemakeJob(job) && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => handleRemakeJob(job.id)} disabled={remakingJobs.has(job.id)}>
                                <RefreshCw className={`mr-2 h-4 w-4 ${remakingJobs.has(job.id) ? 'animate-spin' : ''}`} />
                                {t('remake')}
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
