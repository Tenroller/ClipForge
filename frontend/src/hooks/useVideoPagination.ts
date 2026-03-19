import React, { useState, useCallback, useRef } from 'react';
import { useToast } from '@/hooks/use-toast';
import { type Video } from '@/components/videos/VideoCard';
import { type VideoStatsData } from '@/components/videos/VideoStats';
import { api } from '@/lib/api';

interface VideosResponse {
  videos: Video[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface UseVideoPaginationReturn {
  videos: Video[];
  stats: VideoStatsData | null;
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  offset: number;
  setVideos: React.Dispatch<React.SetStateAction<Video[]>>;
  loadMoreVideos: (params: URLSearchParams) => Promise<void>;
  refreshVideos: (params: URLSearchParams) => Promise<void>;
  loadStats: () => Promise<void>;
}

const DEFAULT_STATS: VideoStatsData = {
  total_videos: 0,
  total_size_mb: 0,
  workflows: {
    moneyprinter: { count: 0, size_mb: 0 },
    brainrot: { count: 0, size_mb: 0 },
  },
  video_types: {
    ai_generated: { count: 0, size_mb: 0 },
    compilation: { count: 0, size_mb: 0 },
  },
};

export function useVideoPagination(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  t: any
): UseVideoPaginationReturn {
  const { toast } = useToast();
  const [videos, setVideos] = useState<Video[]>([]);
  const [stats, setStats] = useState<VideoStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Use a ref to avoid stale closure on rapid "load more" clicks
  const offsetRef = useRef(0);
  // Abort controllers for in-flight requests
  const loadMoreAbortRef = useRef<AbortController | null>(null);
  const refreshAbortRef = useRef<AbortController | null>(null);

  const loadMoreVideos = useCallback(
    async (params: URLSearchParams) => {
      // Abort any in-flight load-more request
      loadMoreAbortRef.current?.abort();
      const controller = new AbortController();
      loadMoreAbortRef.current = controller;

      try {
        setLoadingMore(true);

        // Use the ref for the current offset to avoid stale closures
        const newParams = new URLSearchParams(params);
        newParams.set('offset', offsetRef.current.toString());

        const response = await api.get(`/api/videos/managed?${newParams}`);

        if (controller.signal.aborted) return;

        if (!response.ok) {
          throw new Error(`Failed to load videos: ${response.statusText}`);
        }

        const data: VideosResponse = await response.json();
        setVideos((prev) => [...prev, ...data.videos]);
        const newOffset = offsetRef.current + data.limit;
        offsetRef.current = newOffset;
        setOffset(newOffset);
        setHasMore(data.has_more);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error('Failed to load more videos:', error);
        toast({
          title: t('error'),
          description: t('failedToLoadMore'),
          variant: 'destructive',
        });
      } finally {
        if (!controller.signal.aborted) {
          setLoadingMore(false);
        }
      }
    },
    [toast, t]
  );

  const refreshVideos = useCallback(
    async (params: URLSearchParams) => {
      // Abort any in-flight refresh request
      refreshAbortRef.current?.abort();
      const controller = new AbortController();
      refreshAbortRef.current = controller;

      try {
        setLoading(true);
        offsetRef.current = 0;
        setOffset(0);

        // Override the offset to 0 for refresh
        const newParams = new URLSearchParams(params);
        newParams.set('offset', '0');

        const response = await api.get(`/api/videos/managed?${newParams}`);

        if (controller.signal.aborted) return;

        if (!response.ok) {
          throw new Error(`Failed to load videos: ${response.statusText}`);
        }

        const data: VideosResponse = await response.json();
        setVideos(data.videos);
        offsetRef.current = data.limit;
        setOffset(data.limit);
        setHasMore(data.has_more);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error('Failed to refresh videos:', error);
        toast({
          title: t('error'),
          description: t('failedToLoad'),
          variant: 'destructive',
        });
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    },
    [toast, t]
  );

  const loadStats = useCallback(async () => {
    try {
      const response = await api.get(`/api/videos/stats/managed`);
      if (!response.ok) {
        throw new Error(`Failed to load stats: ${response.statusText}`);
      }
      const data: VideoStatsData = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
      setStats(DEFAULT_STATS);
    }
  }, []);

  return {
    videos,
    stats,
    loading,
    loadingMore,
    hasMore,
    offset,
    setVideos,
    loadMoreVideos,
    refreshVideos,
    loadStats,
  };
}
