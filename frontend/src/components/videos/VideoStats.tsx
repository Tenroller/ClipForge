'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Video as VideoIcon, Film, Brain, HardDrive } from "lucide-react";
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="animate-pulse border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg">
            <CardContent className="p-6">
              <div className="h-10 bg-muted/50 rounded-lg mb-3"></div>
              <div className="h-5 bg-muted/50 rounded"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <Card className="group border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg hover:shadow-2xl hover:border-blue-500/40 hover:-translate-y-1 transition-all duration-300">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
              <VideoIcon className="size-6 text-white" />
            </div>
            <div>
              <div className="text-3xl font-extrabold bg-gradient-to-br from-blue-600 to-cyan-600 bg-clip-text text-transparent">{stats.total_videos}</div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{t('totalVideos')}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="group border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg hover:shadow-2xl hover:border-purple-500/40 hover:-translate-y-1 transition-all duration-300">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
              <HardDrive className="size-6 text-white" />
            </div>
            <div>
              <div className="text-3xl font-extrabold bg-gradient-to-br from-purple-600 to-pink-600 bg-clip-text text-transparent">{formatSize(stats.total_size_mb)}</div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{t('totalSize')}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="group border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg hover:shadow-2xl hover:border-green-500/40 hover:-translate-y-1 transition-all duration-300">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
              <Film className="size-6 text-white" />
            </div>
            <div>
              <div className="text-3xl font-extrabold bg-gradient-to-br from-green-600 to-emerald-600 bg-clip-text text-transparent">{stats.workflows.moneyprinter.count}</div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{t('aiGenerated')}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="group border-2 rounded-2xl bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md shadow-lg hover:shadow-2xl hover:border-orange-500/40 hover:-translate-y-1 transition-all duration-300">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
              <Brain className="size-6 text-white" />
            </div>
            <div>
              <div className="text-3xl font-extrabold bg-gradient-to-br from-orange-600 to-red-600 bg-clip-text text-transparent">{stats.workflows.brainrot.count}</div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{t('compilation')}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
