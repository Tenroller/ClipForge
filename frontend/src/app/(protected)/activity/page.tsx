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
import { Download, Eye, Loader2, RefreshCw, TrendingUp, MoreHorizontal, Activity } from "lucide-react";
import { EmptyState } from '@/components/ui/empty-state';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { JobRecord } from '@/lib/api';
import { getStatusClasses } from '@/lib/status';

export default function ActivityPage() {
  const router = useRouter();
  const t = useTranslations('activity');
  const tCommon = useTranslations('common');
  const { toast } = useToast();
  const { data: jobs = [], isLoading, refetch } = useJobs({ limit: 20, refetchInterval: 10000 });
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

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'N/A';
    }
  };

  // If showing results, render the result panel
  if (selectedResult) {
    return (
      <div className="container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <Activity className="h-8 w-8 text-muted-foreground" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground text-lg">
            {t('description')}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
          className="h-10"
        >
          <RefreshCw className={`size-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          {t('refresh')}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <div className="text-center">
          <div className="text-2xl font-bold">
            {jobs.filter(j => j.status === 'completed' || j.status === 'done').length}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{t('stats.completed')}</p>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold">
            {jobs.filter(j => ['processing', 'running', 'queued'].includes(j.status)).length}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{t('stats.inProgress')}</p>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold">
            {jobs.filter(j => j.status === 'error').length}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{t('stats.failed')}</p>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold">
            {jobs.filter(j => j.status === 'cancelled').length}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{t('stats.cancelled')}</p>
        </div>
      </div>

      {/* Jobs Table */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b">
          <CardTitle className="text-lg">{t('recentJobs')}</CardTitle>
          <CardDescription>
            {t('recentJobsDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Loader2 className="size-8 mb-4 animate-spin" />
              <p>{t('loadingJobs')}</p>
            </div>
          )}
          {!(isLoading && jobs.length === 0) && jobs.length === 0 && (
            <EmptyState
              icon={Activity}
              title={t('noJobs')}
              description={t('noJobsDescription')}
              action={
                <Button asChild variant="default">
                  <a href="/creator">{t('createFirstVideo')}</a>
                </Button>
              }
            />
          )}
          {!(isLoading && jobs.length === 0) && jobs.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">{t('tableHeaders.id')}</TableHead>
                  <TableHead>{t('tableHeaders.workflow')}</TableHead>
                  <TableHead>{t('tableHeaders.status')}</TableHead>
                  <TableHead>{t('tableHeaders.step')}</TableHead>
                  <TableHead>{t('tableHeaders.created')}</TableHead>
                  <TableHead className="text-right">{t('tableHeaders.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id} className="hover:bg-muted/10 transition-colors">
                    <TableCell className="font-mono text-xs font-medium">
                      {job.id.substring(0, 8)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal bg-background">
                        {getWorkflowLabel(job.workflow || '')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusClasses(job.status)}`}>
                        {job.status === 'processing' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                        {job.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                      {job.current_step || '-'}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatDate(job.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-muted">
                            <span className="sr-only">{tCommon('openMenu')}</span>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          <DropdownMenuLabel>{t('tableHeaders.actions')}</DropdownMenuLabel>
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
