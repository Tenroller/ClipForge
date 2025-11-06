'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import VideoCard, { type Video } from '@/components/videos/VideoCard';
import VideoStats, { type VideoStatsData } from '@/components/videos/VideoStats';
import VideoFilters from '@/components/videos/VideoFilters';
import SyncPanel from '@/components/videos/SyncPanel';
import { FaRedo, FaSpinner, FaChevronDown } from 'react-icons/fa';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

interface VideosResponse {
  videos: Video[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export default function VideosPage() {
  const { toast } = useToast();
  const [videos, setVideos] = useState<Video[]>([]);
  const [stats, setStats] = useState<VideoStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [workflowFilter, setWorkflowFilter] = useState('all');
  const [postedFilter, setPostedFilter] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showSyncPanel, setShowSyncPanel] = useState(false);

  const limit = 20;

  // Load videos
  const loadVideos = async (resetOffset = false) => {
    try {
      if (resetOffset) {
        setLoading(true);
        setOffset(0);
      } else {
        setLoadingMore(true);
      }

      const currentOffset = resetOffset ? 0 : offset;
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: currentOffset.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (workflowFilter !== 'all') {
        params.append('workflow', workflowFilter);
      }

      if (postedFilter !== 'all') {
        params.append('posted', postedFilter === 'posted' ? 'true' : 'false');
      }

      const response = await fetch(`${API_BASE}/api/videos/managed?${params}`, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to load videos: ${response.statusText}`);
      }

      const data: VideosResponse = await response.json();

      if (resetOffset) {
        setVideos(data.videos);
        setOffset(data.limit);
      } else {
        setVideos((prev) => [...prev, ...data.videos]);
        setOffset((prev) => prev + data.limit);
      }

      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to load videos:', error);
      toast({
        title: 'Error',
        description: 'Failed to load videos. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // Load stats
  const loadStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/videos/stats/managed`, {
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to load stats: ${response.statusText}`);
      }
      const data: VideoStatsData = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
      setStats({
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
      });
    }
  };

  // Sync videos from jobs
  const syncVideosFromJobs = async () => {
    try {
      setSyncing(true);
      const response = await fetch(`${API_BASE}/api/videos/sync/from-jobs`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to sync videos: ${response.statusText}`);
      }

      const result = await response.json();

      toast({
        title: 'Videos Synced',
        description: `Successfully synced ${result.registered_videos} videos from ${result.processed_jobs} jobs.`,
      });

      loadVideos(true);
      loadStats();
    } catch (error) {
      console.error('Failed to sync videos:', error);
      toast({
        title: 'Sync Failed',
        description: error instanceof Error ? error.message : 'Failed to sync videos from jobs.',
        variant: 'destructive',
      });
    } finally {
      setSyncing(false);
    }
  };

  // Sync orphaned videos
  const syncOrphanedVideos = async () => {
    try {
      setSyncing(true);
      const response = await fetch(`${API_BASE}/api/videos/sync/orphaned`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to sync orphaned videos: ${response.statusText}`);
      }

      const result = await response.json();

      toast({
        title: 'Orphaned Videos Synced',
        description: `Registered ${result.registered_videos} orphaned videos from ${result.scanned_files} files.`,
      });

      loadVideos(true);
      loadStats();
    } catch (error) {
      console.error('Failed to sync orphaned videos:', error);
      toast({
        title: 'Sync Failed',
        description: error instanceof Error ? error.message : 'Failed to sync orphaned videos.',
        variant: 'destructive',
      });
    } finally {
      setSyncing(false);
    }
  };

  // Handle video download
  const handleDownload = (video: Video) => {
    const link = document.createElement('a');
    const downloadUrl = video.download_url || `/api/download?path=${encodeURIComponent(video.file_path || '')}`;
    link.href = `${API_BASE}${downloadUrl}`;
    link.download = video.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    toast({
      title: 'Download Started',
      description: `Downloading ${video.filename}...`,
    });
  };

  // Handle mark as posted
  const handleMarkPosted = async (video: Video) => {
    try {
      const response = await fetch(`${API_BASE}/api/videos/${video.id}/mark-posted`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to mark video as posted');
      }

      toast({
        title: 'Video Marked as Posted',
        description: `${video.filename} has been marked as posted.`,
      });

      // Update local state
      setVideos((prev) =>
        prev.map((v) =>
          v.id === video.id ? { ...v, posted: true, posted_at: new Date().toISOString() } : v
        )
      );
      loadStats();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to mark video as posted.',
        variant: 'destructive',
      });
    }
  };

  // Initial load
  useEffect(() => {
    loadVideos(true);
    loadStats();
  }, [workflowFilter, postedFilter, sortBy, sortOrder]);

  // Filter videos by search term
  const filteredVideos = videos.filter(
    (video) =>
      video.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      video.job_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="container-page">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Video Gallery</h1>
          <p className="text-muted-foreground mt-2">Browse and manage generated videos</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSyncPanel(!showSyncPanel)}
          >
            {showSyncPanel ? 'Hide' : 'Show'} Sync
          </Button>
          <Button variant="outline" size="sm" onClick={() => loadVideos(true)} disabled={loading}>
            {loading ? (
              <FaSpinner className="size-4 animate-spin" />
            ) : (
              <FaRedo className="size-4" />
            )}
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Stats */}
        <VideoStats stats={stats} loading={loading && !stats} />

        {/* Sync Panel */}
        {showSyncPanel && (
          <SyncPanel
            onSyncFromJobs={syncVideosFromJobs}
            onSyncOrphaned={syncOrphanedVideos}
            syncing={syncing}
          />
        )}

        {/* Filters */}
        <VideoFilters
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          workflowFilter={workflowFilter}
          onWorkflowFilterChange={setWorkflowFilter}
          postedFilter={postedFilter}
          onPostedFilterChange={setPostedFilter}
          sortBy={sortBy}
          onSortByChange={setSortBy}
          sortOrder={sortOrder}
          onSortOrderChange={setSortOrder}
        />

        {/* Videos List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <FaSpinner className="size-8 animate-spin text-primary" />
          </div>
        ) : filteredVideos.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No videos found</p>
            <p className="text-sm text-muted-foreground mt-2">
              {searchTerm
                ? 'Try adjusting your search or filters'
                : 'Generate some videos to see them here'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredVideos.map((video) => (
              <VideoCard
                key={video.id}
                video={video}
                onDownload={handleDownload}
                onMarkPosted={handleMarkPosted}
              />
            ))}

            {/* Load More Button */}
            {hasMore && !searchTerm && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="outline"
                  onClick={() => loadVideos(false)}
                  disabled={loadingMore}
                >
                  {loadingMore ? (
                    <>
                      <FaSpinner className="size-4 mr-2 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <FaChevronDown className="size-4 mr-2" />
                      Load More
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
