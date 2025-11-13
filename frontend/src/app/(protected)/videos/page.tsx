'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import VideoCard, { type Video } from '@/components/videos/VideoCard';
import GridVideoCard from '@/components/videos/GridVideoCard';
import VideoCardSkeleton from '@/components/videos/VideoCardSkeleton';
import VideoPreviewModal from '@/components/videos/VideoPreviewModal';
import BulkActionsBar from '@/components/videos/BulkActionsBar';
import VideoStats, { type VideoStatsData } from '@/components/videos/VideoStats';
import VideoFilters from '@/components/videos/VideoFilters';
import SyncPanel from '@/components/videos/SyncPanel';
import { ChevronDown, LayoutGrid, List, Loader2, RefreshCw, Film } from "lucide-react";

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
  const t = useTranslations('videos');
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

  // View mode and bulk selection
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());
  const [previewVideo, setPreviewVideo] = useState<Video | null>(null);

  // Delete confirmation dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [videoToDelete, setVideoToDelete] = useState<Video | null>(null);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);

  const limit = 20;

  // Load view mode from localStorage
  useEffect(() => {
    const savedViewMode = localStorage.getItem('videosViewMode') as 'grid' | 'list' | null;
    if (savedViewMode) {
      setViewMode(savedViewMode);
    }
  }, []);

  // Save view mode to localStorage
  const handleViewModeChange = (mode: 'grid' | 'list') => {
    setViewMode(mode);
    localStorage.setItem('videosViewMode', mode);
  };

  // Load more videos (for pagination)
  const loadMoreVideos = useCallback(async () => {
    try {
      setLoadingMore(true);

      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
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
      setVideos((prev) => [...prev, ...data.videos]);
      setOffset((prev) => prev + data.limit);
      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to load more videos:', error);
      toast({
        title: t('error'),
        description: t('failedToLoadMore'),
        variant: 'destructive',
      });
    } finally {
      setLoadingMore(false);
    }
  }, [workflowFilter, postedFilter, sortBy, sortOrder, offset, toast, t]);

  // Refresh function for manual refresh
  const refreshVideos = useCallback(async () => {
    try {
      setLoading(true);
      setOffset(0);

      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: '0',
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
      setVideos(data.videos);
      setOffset(data.limit);
      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to refresh videos:', error);
      toast({
        title: t('error'),
        description: t('failedToLoad'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [workflowFilter, postedFilter, sortBy, sortOrder, toast, t]);

  // Load stats
  const loadStats = useCallback(async () => {
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
  }, []);

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
        title: t('sync.videosSynced'),
        description: t('sync.syncedFromJobs', { 
          count: result.registered_videos, 
          jobs: result.processed_jobs 
        }),
      });

      refreshVideos();
      loadStats();
    } catch (error) {
      console.error('Failed to sync videos:', error);
      toast({
        title: t('sync.syncFailed'),
        description: error instanceof Error ? error.message : t('sync.failedToSync'),
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
        title: t('sync.orphanedSynced'),
        description: t('sync.registeredOrphaned', { 
          count: result.registered_videos, 
          files: result.scanned_files 
        }),
      });

      refreshVideos();
      loadStats();
    } catch (error) {
      console.error('Failed to sync orphaned videos:', error);
      toast({
        title: t('sync.syncFailed'),
        description: error instanceof Error ? error.message : t('sync.failedToSyncOrphaned'),
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
      title: t('downloadStarted'),
      description: t('downloading', { filename: video.filename }),
    });
  };

  // Handle mark as posted
  const handleMarkPosted = async (video: Video) => {
    try {
      const response = await fetch(`${API_BASE}/api/videos/managed/${video.id}/mark-posted`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to mark video as posted');
      }

      toast({
        title: t('videoMarkedPosted'),
        description: t('markedAsPosted', { filename: video.filename }),
      });

      // Update local state
      setVideos((prev) =>
        prev.map((v) =>
          v.id === video.id ? { ...v, posted: true, posted_at: new Date().toISOString() } : v
        )
      );
      loadStats();
    } catch {
      toast({
        title: t('error'),
        description: t('failedToMark'),
        variant: 'destructive',
      });
    }
  };

  // Handle delete video
  const handleDeleteClick = (video: Video) => {
    setVideoToDelete(video);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!videoToDelete) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/videos/managed/${videoToDelete.id}?delete_file=true`,
        {
          method: 'DELETE',
          credentials: 'include',
        }
      );

      if (!response.ok) {
        throw new Error('Failed to delete video');
      }

      toast({
        title: t('videoDeleted'),
        description: t('permanentlyDeleted', { filename: videoToDelete.filename }),
      });

      // Remove from local state
      setVideos((prev) => prev.filter((v) => v.id !== videoToDelete.id));

      // Remove from selection if selected
      setSelectedVideos((prev) => {
        const newSet = new Set(prev);
        newSet.delete(videoToDelete.id);
        return newSet;
      });

      loadStats();
    } catch {
      toast({
        title: t('error'),
        description: t('failedToDelete'),
        variant: 'destructive',
      });
    } finally {
      setDeleteDialogOpen(false);
      setVideoToDelete(null);
    }
  };

  // Handle bulk selection
  const handleVideoSelect = (video: Video, selected: boolean) => {
    setSelectedVideos((prev) => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(video.id);
      } else {
        newSet.delete(video.id);
      }
      return newSet;
    });
  };

  const handleClearSelection = () => {
    setSelectedVideos(new Set());
  };

  // Bulk operations
  const handleBulkDownload = () => {
    const selected = filteredVideos.filter((v) => selectedVideos.has(v.id));
    selected.forEach((video) => handleDownload(video));
    toast({
      title: t('bulkDownloadStarted'),
      description: t('downloadingMultiple', { count: selected.length }),
    });
  };

  const handleBulkMarkPosted = async () => {
    const selected = filteredVideos.filter((v) => selectedVideos.has(v.id) && !v.posted);

    try {
      await Promise.all(selected.map((video) => handleMarkPosted(video)));
      setSelectedVideos(new Set());
      toast({
        title: t('bulkOperationComplete'),
        description: t('markedMultiple', { count: selected.length }),
      });
    } catch {
      toast({
        title: t('error'),
        description: t('failedToMarkSome'),
        variant: 'destructive',
      });
    }
  };

  const handleBulkDeleteClick = () => {
    setBulkDeleteDialogOpen(true);
  };

  const handleBulkDeleteConfirm = async () => {
    const selected = filteredVideos.filter((v) => selectedVideos.has(v.id));
    const selectedCount = selected.length;

    try {
      // Delete videos in parallel
      await Promise.all(
        selected.map(async (video) => {
          const response = await fetch(
            `${API_BASE}/api/videos/managed/${video.id}?delete_file=true`,
            {
              method: 'DELETE',
              credentials: 'include',
            }
          );

          if (!response.ok) {
            throw new Error(`Failed to delete ${video.filename}`);
          }
        })
      );

      // Remove from local state
      setVideos((prev) => prev.filter((v) => !selectedVideos.has(v.id)));

      // Clear selection
      setSelectedVideos(new Set());

      toast({
        title: t('videosDeleted'),
        description: t('successfullyDeleted', { 
          count: selectedCount,
          plural: selectedCount !== 1 ? 's' : ''
        }),
      });

      loadStats();
    } catch {
      toast({
        title: t('error'),
        description: t('failedToDeleteSome'),
        variant: 'destructive',
      });
    } finally {
      setBulkDeleteDialogOpen(false);
    }
  };

  // Initial load effect
  useEffect(() => {
    const initialLoad = async () => {
      try {
        setLoading(true);
        setOffset(0);

        const params = new URLSearchParams({
          limit: limit.toString(),
          offset: '0',
          sort_by: sortBy,
          sort_order: sortOrder,
        });

        if (workflowFilter !== 'all') {
          params.append('workflow', workflowFilter);
        }

        if (postedFilter !== 'all') {
          params.append('posted', postedFilter === 'posted' ? 'true' : 'false');
        }

        // Load videos and stats in parallel
        const [videosResponse, statsResponse] = await Promise.all([
          fetch(`${API_BASE}/api/videos/managed?${params}`, {
            credentials: 'include',
          }),
          fetch(`${API_BASE}/api/videos/stats/managed`, {
            credentials: 'include',
          }),
        ]);

        if (!videosResponse.ok) {
          throw new Error(`Failed to load videos: ${videosResponse.statusText}`);
        }

        const videosData: VideosResponse = await videosResponse.json();
        setVideos(videosData.videos);
        setOffset(videosData.limit);
        setHasMore(videosData.has_more);

        if (statsResponse.ok) {
          const statsData: VideoStatsData = await statsResponse.json();
          setStats(statsData);
        } else {
          console.error('Failed to load stats:', statsResponse.statusText);
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
      } catch (error) {
        console.error('Failed to load initial data:', error);
        toast({
          title: t('error'),
          description: t('failedToLoad'),
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    initialLoad();
  }, [workflowFilter, postedFilter, sortBy, sortOrder, toast, t]);

  // Filter videos by search term
  const filteredVideos = videos.filter(
    (video) =>
      video.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      video.job_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Count selected unposted videos
  const selectedUnpostedCount = filteredVideos.filter(
    (v) => selectedVideos.has(v.id) && !v.posted
  ).length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="inline-block">
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
              {t('title')}
            </h1>
            <div className="h-1 w-24 bg-gradient-to-r from-primary to-accent rounded-full mt-2" />
          </div>
          <p className="text-base text-muted-foreground max-w-2xl">
            {t('description')}
            {selectedVideos.size > 0 && (
              <span className="ml-2 text-primary font-semibold">
                · {selectedVideos.size} {t('selected')}
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap justify-end">
          {/* View Toggle */}
          <div className="flex gap-0.5 border rounded-lg p-0.5 bg-muted/50">
            <Button
              variant={viewMode === 'grid' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleViewModeChange('grid')}
              className="h-8 px-3"
            >
              <LayoutGrid className="size-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleViewModeChange('list')}
              className="h-8 px-3"
            >
              <List className="size-4" />
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSyncPanel(!showSyncPanel)}
          >
            {showSyncPanel ? t('hideSync') : t('showSync')}
          </Button>
          <Button variant="outline" size="sm" onClick={refreshVideos} disabled={loading}>
            {loading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
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
          viewMode === 'grid' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-5">
              {Array.from({ length: 8 }).map((_, i) => (
                <VideoCardSkeleton key={i} variant="grid" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <VideoCardSkeleton key={i} variant="list" />
              ))}
            </div>
          )
        ) : filteredVideos.length === 0 ? (
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md">
            <CardContent className="p-12">
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
                  <Film className="size-8 text-muted-foreground" />
                </div>
                <p className="text-lg font-medium text-muted-foreground">{t('noVideos')}</p>
                <p className="text-sm text-muted-foreground mt-2">
                  {searchTerm
                    ? t('tryAdjusting')
                    : t('generateToSee')}
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {viewMode === 'grid' ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-5">
                {filteredVideos.map((video) => (
                  <GridVideoCard
                    key={video.id}
                    video={video}
                    onDownload={handleDownload}
                    onPlay={setPreviewVideo}
                    onMarkPosted={handleMarkPosted}
                    onDelete={handleDeleteClick}
                    selected={selectedVideos.has(video.id)}
                    onSelect={handleVideoSelect}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredVideos.map((video) => (
                  <VideoCard
                    key={video.id}
                    video={video}
                    onDownload={handleDownload}
                    onPlay={setPreviewVideo}
                    onMarkPosted={handleMarkPosted}
                    onDelete={handleDeleteClick}
                    selected={selectedVideos.has(video.id)}
                    onSelect={handleVideoSelect}
                  />
                ))}
              </div>
            )}

            {/* Load More Button */}
            {hasMore && !searchTerm && (
              <div className="flex justify-center pt-6">
                <Button
                  variant="outline"
                  onClick={loadMoreVideos}
                  disabled={loadingMore}
                >
                  {loadingMore ? (
                    <>
                      <Loader2 className="size-4 mr-2 animate-spin" />
                      {t('loading')}
                    </>
                  ) : (
                    <>
                      <ChevronDown className="size-4 mr-2" />
                      {t('loadMore')}
                    </>
                  )}
                </Button>
              </div>
            )}

            {/* Loading More Skeletons */}
            {loadingMore && (
              viewMode === 'grid' ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-5 mt-5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <VideoCardSkeleton key={i} variant="grid" />
                  ))}
                </div>
              ) : (
                <div className="space-y-3 mt-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <VideoCardSkeleton key={i} variant="list" />
                  ))}
                </div>
              )
            )}
          </>
        )}
      </div>

      {/* Video Preview Modal */}
      <VideoPreviewModal
        video={previewVideo}
        open={!!previewVideo}
        onClose={() => setPreviewVideo(null)}
        onDownload={handleDownload}
        onMarkPosted={handleMarkPosted}
      />

      {/* Bulk Actions Bar */}
      <BulkActionsBar
        selectedCount={selectedVideos.size}
        onDownloadAll={handleBulkDownload}
        onMarkAllPosted={handleBulkMarkPosted}
        onDeleteAll={handleBulkDeleteClick}
        onClearSelection={handleClearSelection}
        totalUnposted={selectedUnpostedCount}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('dialog.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t.rich('dialog.deleteDescription', { 
                filename: videoToDelete?.filename || '',
                strong: (chunks) => <strong>{chunks}</strong>
              })}
              <br />
              <br />
              {t('dialog.deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('dialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('dialog.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Confirmation Dialog */}
      <AlertDialog open={bulkDeleteDialogOpen} onOpenChange={setBulkDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('dialog.deleteMultipleTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t.rich('dialog.deleteMultipleDescription', { 
                count: selectedVideos.size,
                plural: selectedVideos.size !== 1 ? 's' : '',
                strong: (chunks) => <strong>{chunks}</strong>
              })}
              <br />
              <br />
              {t('dialog.deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('dialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleBulkDeleteConfirm} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('dialog.deleteAll')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
