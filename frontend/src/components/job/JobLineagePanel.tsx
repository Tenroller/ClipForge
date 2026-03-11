'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import {
  Network,
  Loader2,
  RotateCw,
  RefreshCw,
  CheckCircle,
  XCircle,
  Pause,
  Clock,
  ChevronRight,
  Copy,
} from "lucide-react";
import { useJobLineage } from '@/hooks/use-jobs';
import { EmptyState } from '@/components/ui/empty-state';
import type { LineageRecord } from '@/lib/api';

interface JobLineagePanelProps {
  jobId: string;
  className?: string;
}

export default function JobLineagePanel({ jobId, className }: JobLineagePanelProps) {
  const t = useTranslations('common');
  const { toast } = useToast();
  const router = useRouter();
  const { data, isLoading, error, refetch } = useJobLineage(jobId);
  const [lastFetched, setLastFetched] = useState<number>(Date.now());

  const handleRefresh = () => {
    refetch();
    setLastFetched(Date.now());
  };

  const statusBadge = (status?: string) => {
    switch (status) {
      case 'done':
      case 'completed':
        return (
          <Badge variant="secondary" className="gap-1">
            <CheckCircle className="size-3" /> done
          </Badge>
        );
      case 'error':
        return (
          <Badge variant="destructive" className="gap-1">
            <XCircle className="size-3" /> error
          </Badge>
        );
      case 'cancelled':
        return (
          <Badge variant="outline" className="gap-1">
            <Pause className="size-3" /> cancelled
          </Badge>
        );
      case 'running':
      case 'processing':
        return (
          <Badge variant="default" className="gap-1">
            <Loader2 className="size-3 animate-spin" /> running
          </Badge>
        );
      case 'queued':
        return (
          <Badge variant="outline" className="gap-1">
            <Clock className="size-3" /> queued
          </Badge>
        );
      default:
        return <Badge variant="outline">unknown</Badge>;
    }
  };

  const shortId = (id: string) => id.slice(0, 8);

  const copyId = (id: string) => {
    try {
      navigator.clipboard.writeText(id);
      toast({
        title: 'Copied',
        description: 'Job ID copied to clipboard',
      });
    } catch {
      toast({
        title: 'Failed to Copy',
        description: 'Could not copy job ID to clipboard',
        variant: 'destructive',
      });
    }
  };

  const ancestors = data?.ancestors || [];
  const descendants = data?.descendants || [];
  const chain = [...ancestors, { id: jobId }];

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Network className="size-5" />
            Lineage
          </CardTitle>
          <CardDescription>Ancestry & resume attempts for this job</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {lastFetched && (
            <span className="text-xs text-muted-foreground hidden md:inline">
              {new Date(lastFetched).toLocaleTimeString()}
            </span>
          )}
          <Button size="sm" variant="outline" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`size-3 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <div className="p-3 border border-red-200 bg-red-50 rounded text-sm text-red-700 dark:bg-red-950/30 dark:border-red-800/50">
            {error instanceof Error ? error.message : 'Failed to load lineage'}
          </div>
        )}

        {/* Ancestor Chain */}
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
            Ancestor Chain
          </div>
          {isLoading && chain.length === 1 ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> {t('loadingLineage')}
            </div>
          ) : chain.length === 1 && ancestors.length === 0 ? (
            <div className="text-sm text-muted-foreground">This job has no ancestors (root of its chain).</div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {chain.map((rec, idx) => {
                const isCurrent = rec.id === jobId;
                const ancestorMeta = ancestors.find((a) => a.id === rec.id);
                return (
                  <div key={rec.id} className="flex items-center gap-2">
                    <div
                      className={`group flex items-center gap-2 px-2 py-1 rounded border text-xs font-mono cursor-pointer transition ${isCurrent
                          ? 'bg-blue-50 dark:bg-blue-950/30 border-blue-300 dark:border-blue-700'
                          : 'bg-muted/40 border-border/50 hover:bg-muted'
                        } `}
                      onClick={() => {
                        if (!isCurrent) router.push(`/job/${rec.id}`);
                      }}
                      title={isCurrent ? 'Current job' : 'View this ancestor job'}
                    >
                      <span>{shortId(rec.id)}</span>
                      {ancestorMeta?.resume_attempt && ancestorMeta.resume_attempt > 1 && (
                        <Badge variant="outline" className="text-[10px] py-0 px-1">
                          #{ancestorMeta.resume_attempt}
                        </Badge>
                      )}
                      {isCurrent && (
                        <Badge variant="secondary" className="text-[10px] py-0 px-1">
                          current
                        </Badge>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          copyId(rec.id);
                        }}
                        className="opacity-40 group-hover:opacity-100 transition"
                        title="Copy job ID"
                      >
                        <Copy className="size-3" />
                      </button>
                    </div>
                    {idx < chain.length - 1 && <ChevronRight className="size-3 text-muted-foreground" />}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Descendants */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Descendants</div>
            {descendants.length > 0 && (
              <div className="text-xs text-muted-foreground">
                {descendants.length} job{descendants.length === 1 ? '' : 's'}
              </div>
            )}
          </div>
          {isLoading && descendants.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> {t('loadingDescendants')}
            </div>
          ) : descendants.length === 0 ? (
            <EmptyState
              icon={Network}
              title="No descendant jobs yet"
              description="Resumed jobs will appear here."
              className="py-8"
            />
          ) : (
            <div className="border rounded-md divide-y bg-muted/20 dark:divide-border/40">
              {descendants.map((d) => (
                <div
                  key={d.id}
                  className="p-2 text-xs flex flex-wrap md:flex-nowrap items-center gap-2 hover:bg-background/60 cursor-pointer transition"
                  onClick={() => router.push(`/job/${d.id}`)}
                  title="View this descendant job"
                >
                  <span className="font-mono w-24 truncate">{shortId(d.id)}</span>
                  <div className="flex items-center gap-2">{statusBadge(d.status)}</div>
                  {d.resume_attempt && (
                    <Badge variant="outline" className="text-[10px] py-0 px-1">
                      attempt {d.resume_attempt}
                    </Badge>
                  )}
                  {d.children_count && d.children_count > 0 && (
                    <Badge variant="secondary" className="text-[10px] py-0 px-1">
                      {d.children_count} child{d.children_count === 1 ? '' : 'ren'}
                    </Badge>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyId(d.id);
                      }}
                      className="opacity-40 hover:opacity-100 transition"
                      title="Copy job ID"
                    >
                      <Copy className="size-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
