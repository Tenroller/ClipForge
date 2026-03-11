'use client';

import { useTranslations } from 'next-intl';

export interface VideoStatsData {
  total_videos: number;
  total_size_mb: number;
  workflows: {
    moneyprinter: { count: number; size_mb: number };
    brainrot: { count: number; size_mb: number };
  };
  video_types: {
    ai_generated: { count: number; size_mb: number };
    compilation: { count: number; size_mb: number };
  };
}

interface VideoStatsProps {
  stats: VideoStatsData | null;
  loading?: boolean;
}

export default function VideoStats({ stats, loading }: VideoStatsProps) {
  const t = useTranslations('videos.stats');

  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
    return `${mb.toFixed(2)} MB`;
  };

  if (loading || !stats) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-9 w-24 bg-muted animate-pulse rounded" />
            <div className="h-3 w-20 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
      <div>
        <div className="text-3xl font-bold">{stats.total_videos}</div>
        <p className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{t('totalVideos')}</p>
      </div>

      <div>
        <div className="text-3xl font-bold">{formatSize(stats.total_size_mb)}</div>
        <p className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{t('totalSize')}</p>
      </div>

      <div>
        <div className="text-3xl font-bold">{stats.workflows.moneyprinter.count}</div>
        <p className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{t('aiGenerated')}</p>
      </div>

      <div>
        <div className="text-3xl font-bold">{stats.workflows.brainrot.count}</div>
        <p className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{t('compilation')}</p>
      </div>
    </div>
  );
}
