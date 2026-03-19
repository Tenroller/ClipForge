'use client';

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { useJobs } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  LayoutDashboard,
  Loader2,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  Film,
  TrendingUp,
  BarChart3,
} from 'lucide-react';
import type { JobRecord } from '@/lib/api';
import { formatDuration } from '@/lib/formatDuration';
import { getStatusClasses, getStatusIconColor } from '@/lib/status';
import Link from 'next/link';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(dateString: string | undefined, t: (key: string, params?: Record<string, number>) => string): string {
  if (!dateString) return '';
  try {
    const diff = Date.now() - new Date(dateString).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return t('relativeTime.justNow');
    if (minutes < 60) return t('relativeTime.minutesAgo', { count: minutes });
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return t('relativeTime.hoursAgo', { count: hours });
    const days = Math.floor(hours / 24);
    return t('relativeTime.daysAgo', { count: days });
  } catch {
    return '';
  }
}

function getWorkflowLabel(workflow: string, t: (key: string) => string): string {
  switch (workflow) {
    case 'moneyprinter':
      return t('workflowLabels.moneyprinter');
    case 'brainrot':
      return t('workflowLabels.brainrot');
    case 'podcastclips':
      return t('workflowLabels.podcastclips');
    default:
      return workflow;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconColor,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className={`rounded-lg p-3 ${iconColor ?? 'bg-muted'}`}>
            <Icon className="size-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/** Pure-CSS vertical bar chart for jobs over the last 7 days. */
function JobsOverTimeChart({ jobs }: { jobs: JobRecord[] }) {
  const t = useTranslations('analyticsDashboard');
  const days = useMemo(() => {
    const result: { label: string; count: number }[] = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dayStr = d.toISOString().slice(0, 10);
      const label = d.toLocaleDateString(undefined, { weekday: 'short' });
      const count = jobs.filter((j) => {
        const created = j.created_at;
        if (!created) return false;
        return created.slice(0, 10) === dayStr;
      }).length;
      result.push({ label, count });
    }
    return result;
  }, [jobs]);

  const maxCount = Math.max(...days.map((d) => d.count), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('jobsOverTime')}</CardTitle>
        <CardDescription>{t('last7Days')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2 h-40">
          {days.map((day) => {
            const pct = (day.count / maxCount) * 100;
            return (
              <div key={day.label} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-xs font-medium text-muted-foreground">{day.count}</span>
                <div className="w-full rounded-t-sm bg-muted relative" style={{ height: '100%' }}>
                  <div
                    className="absolute bottom-0 left-0 right-0 rounded-t-sm bg-primary transition-all duration-500"
                    style={{ height: `${Math.max(pct, 2)}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">{day.label}</span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

/** Horizontal bar chart for jobs by workflow. */
function WorkflowChart({ jobs }: { jobs: JobRecord[] }) {
  const t = useTranslations('analyticsDashboard');
  const workflows = useMemo(() => {
    const map: Record<string, number> = {};
    for (const job of jobs) {
      const wf = job.workflow || 'unknown';
      map[wf] = (map[wf] || 0) + 1;
    }
    return Object.entries(map)
      .map(([name, count]) => ({ name, count, label: getWorkflowLabel(name, t) }))
      .sort((a, b) => b.count - a.count);
  }, [jobs, t]);

  const maxCount = Math.max(...workflows.map((w) => w.count), 1);

  const barColors: Record<string, string> = {
    moneyprinter: 'bg-info',
    brainrot: 'bg-warning',
    podcastclips: 'bg-success',
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('jobsByWorkflow')}</CardTitle>
        <CardDescription>{t('allTimeDistribution')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {workflows.length === 0 && (
          <p className="text-sm text-muted-foreground">{t('noData')}</p>
        )}
        {workflows.map((wf) => {
          const pct = (wf.count / maxCount) * 100;
          return (
            <div key={wf.name} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{wf.label}</span>
                <span className="text-muted-foreground">{wf.count}</span>
              </div>
              <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${barColors[wf.name] ?? 'bg-primary'}`}
                  style={{ width: `${Math.max(pct, 2)}%` }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

/** Status distribution using progress bars. */
function StatusDistribution({ jobs }: { jobs: JobRecord[] }) {
  const t = useTranslations('analyticsDashboard');
  const statuses = useMemo(() => {
    const total = jobs.length || 1;
    const counts: Record<string, number> = {};
    for (const job of jobs) {
      const s = job.status || 'unknown';
      counts[s] = (counts[s] || 0) + 1;
    }
    const statusConfig: { key: string; label: string; color: string }[] = [
      { key: 'done', label: t('statusDone'), color: 'bg-success' },
      { key: 'completed', label: t('statusCompleted'), color: 'bg-success' },
      { key: 'error', label: t('statusError'), color: 'bg-destructive' },
      { key: 'cancelled', label: t('statusCancelled'), color: 'bg-muted-foreground' },
      { key: 'processing', label: t('statusProcessing'), color: 'bg-info' },
      { key: 'running', label: t('statusRunning'), color: 'bg-info' },
      { key: 'queued', label: t('statusQueued'), color: 'bg-warning' },
    ];
    return statusConfig
      .filter((s) => (counts[s.key] ?? 0) > 0)
      .map((s) => ({
        ...s,
        count: counts[s.key] ?? 0,
        pct: ((counts[s.key] ?? 0) / total) * 100,
      }));
  }, [jobs, t]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('statusDistribution')}</CardTitle>
        <CardDescription>{t('jobStatusBreakdown')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {statuses.length === 0 && (
          <p className="text-sm text-muted-foreground">{t('noData')}</p>
        )}
        {statuses.map((s) => (
          <div key={s.key} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{s.label}</span>
              <span className="text-muted-foreground">
                {s.count} ({s.pct.toFixed(0)}%)
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${s.color}`}
                style={{ width: `${Math.max(s.pct, 1)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** Recent activity list (last 10 jobs). */
function RecentActivity({ jobs }: { jobs: JobRecord[] }) {
  const t = useTranslations('analyticsDashboard');
  const recent = jobs.slice(0, 10);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('recentActivity')}</CardTitle>
        <CardDescription>{t('last10Jobs')}</CardDescription>
      </CardHeader>
      <CardContent>
        {recent.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">{t('noRecentJobs')}</p>
        ) : (
          <div className="space-y-3">
            {recent.map((job) => (
              <Link
                key={job.id}
                href={`/job/${job.id}`}
                className="flex items-center justify-between gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="shrink-0">
                    {job.status === 'done' || job.status === 'completed' ? (
                      <CheckCircle2 className={`size-4 ${getStatusIconColor('done')}`} />
                    ) : job.status === 'error' ? (
                      <XCircle className={`size-4 ${getStatusIconColor('error')}`} />
                    ) : ['processing', 'running', 'queued'].includes(job.status) ? (
                      <Loader2 className={`size-4 ${getStatusIconColor('running')} animate-spin`} />
                    ) : (
                      <Clock className="size-4 text-muted-foreground" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {getWorkflowLabel(job.workflow || '', t)}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {job.id.substring(0, 8)}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {job.current_step || job.step || '-'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${getStatusClasses(job.status)}`}
                  >
                    {job.status}
                  </span>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {relativeTime(job.created_at, t)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const t = useTranslations('analyticsDashboard');
  const { data: jobs = [], isLoading, refetch } = useJobs({ limit: 100, refetchInterval: 15000 });

  // Aggregate stats
  const stats = useMemo(() => {
    const total = jobs.length;
    const completed = jobs.filter(
      (j) => j.status === 'completed' || j.status === 'done'
    ).length;
    const failed = jobs.filter((j) => j.status === 'error').length;
    const successRate = total > 0 ? ((completed / Math.max(completed + failed, 1)) * 100).toFixed(0) : '0';

    // Average duration (from jobs that have duration_seconds)
    const durJobs = jobs.filter((j) => typeof j.duration_seconds === 'number' && j.duration_seconds > 0);
    const avgDuration =
      durJobs.length > 0
        ? durJobs.reduce((sum, j) => sum + (j.duration_seconds ?? 0), 0) / durJobs.length
        : 0;

    return { total, completed, failed, successRate, avgDuration };
  }, [jobs]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <LayoutDashboard className="h-8 w-8 text-muted-foreground" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground text-lg">{t('description')}</p>
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

      {/* Loading state */}
      {isLoading && jobs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
          <Loader2 className="size-8 mb-4 animate-spin" />
          <p>{t('loading')}</p>
        </div>
      )}

      {/* Content */}
      {!(isLoading && jobs.length === 0) && (
        <>
          {/* Summary Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
            <SummaryCard
              title={t('totalJobs')}
              value={stats.total}
              subtitle={t('allTime')}
              icon={BarChart3}
              iconColor="bg-info/10 text-info"
            />
            <SummaryCard
              title={t('successRate')}
              value={`${stats.successRate}%`}
              subtitle={`${stats.completed} ${t('completed')} / ${stats.failed} ${t('failed')}`}
              icon={TrendingUp}
              iconColor="bg-success/10 text-success"
            />
            <SummaryCard
              title={t('videosGenerated')}
              value={stats.completed}
              subtitle={t('totalCompleted')}
              icon={Film}
              iconColor="bg-accent/10 text-accent"
            />
            <SummaryCard
              title={t('avgGenerationTime')}
              value={stats.avgDuration > 0 ? formatDuration(stats.avgDuration) : '--'}
              subtitle={t('perJob')}
              icon={Clock}
              iconColor="bg-warning/10 text-warning"
            />
          </div>

          {/* Charts row */}
          <div className="grid gap-6 lg:grid-cols-3 mb-8">
            <JobsOverTimeChart jobs={jobs} />
            <WorkflowChart jobs={jobs} />
            <StatusDistribution jobs={jobs} />
          </div>

          {/* Recent Activity */}
          <RecentActivity jobs={jobs} />
        </>
      )}
    </div>
  );
}
