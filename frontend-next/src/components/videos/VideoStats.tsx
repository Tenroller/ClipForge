'use client';

import { Card, CardContent } from '@/components/ui/card';
import { FaVideo, FaFilm, FaBrain, FaHdd } from 'react-icons/fa';

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
  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
    return `${mb.toFixed(2)} MB`;
  };

  if (loading || !stats) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="pt-6">
              <div className="h-8 bg-muted rounded mb-2"></div>
              <div className="h-4 bg-muted rounded"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-600 flex items-center justify-center">
              <FaVideo className="size-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.total_videos}</div>
              <p className="text-xs text-muted-foreground">Total Videos</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 flex items-center justify-center">
              <FaHdd className="size-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-bold">{formatSize(stats.total_size_mb)}</div>
              <p className="text-xs text-muted-foreground">Total Size</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 flex items-center justify-center">
              <FaFilm className="size-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.workflows.moneyprinter.count}</div>
              <p className="text-xs text-muted-foreground">AI Generated</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg bg-gradient-to-r from-orange-500 to-red-600 flex items-center justify-center">
              <FaBrain className="size-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.workflows.brainrot.count}</div>
              <p className="text-xs text-muted-foreground">Compilations</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
