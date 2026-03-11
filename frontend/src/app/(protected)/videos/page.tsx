'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
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
import { useVideoFilters } from '@/hooks/useVideoFilters';
import { useVideoSelection } from '@/hooks/useVideoSelection';
import { useVideoPagination } from '@/hooks/useVideoPagination';
import { type Video } from '@/components/videos/VideoCard';
import VideoPreviewModal from '@/components/videos/VideoPreviewModal';
import VideoStats from '@/components/videos/VideoStats';
import VideoFilters from '@/components/videos/VideoFilters';
import VideoGrid from '@/components/videos/VideoGrid';
import VideoBulkActions from '@/components/videos/VideoBulkActions';
import SyncPanel from '@/components/videos/SyncPanel';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { LayoutGrid, List, PlaySquare, RefreshCw, Settings2 } from 'lucide-react';
import { api, API_BASE } from '@/lib/api';

export default function VideosPage() {
  const { toast } = useToast();
  const t = useTranslations('videos');

  // Custom hooks
  const filters = useVideoFilters();
  const selection = useVideoSelection();
  const pagination = useVideoPagination(t);

  // Local UI state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [syncing, setSyncing] = useState(false);
  const [showSyncPanel, setShowSyncPanel] = useState(false);
  const [previewVideo, setPreviewVideo] = useState<Video | null>(null);

  // Delete confirmation dialogs
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [videoToDelete, setVideoToDelete] = useState<Video | null>(null);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);

  // Load view mode from localStorage
  useEffect(() => {
    const savedViewMode = localStorage.getItem('videosViewMode') as 'grid' | 'list' | null;
    if (savedViewMode) {
      setViewMode(savedViewMode);
    }
  }, []);

  const handleViewModeChange = (mode: 'grid' | 'list') => {
    setViewMode(mode);
    localStorage.setItem('videosViewMode', mode);
  };

  // Sync operations
  const syncVideosFromJobs = async () => {
    try {
      setSyncing(true);
      const response = await api.post(`/api/videos/sync/from-jobs`);

      if (!response.ok) {
        throw new Error(`Failed to sync videos: ${response.statusText}`);
      }

      const result = await response.json();

      toast({
        title: t('sync.videosSynced'),
        description: t('sync.syncedFromJobs', {
          count: result.registered_videos,
          jobs: result.processed_jobs,
        }),
      });

      pagination.refreshVideos(filters.buildSearchParams());
      pagination.loadStats();
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

  const syncOrphanedVideos = async () => {
    try {
      setSyncing(true);
      const response = await api.post(`/api/videos/sync/orphaned`);

      if (!response.ok) {
        throw new Error(`Failed to sync orphaned videos: ${response.statusText}`);
      }

      const result = await response.json();

      toast({
        title: t('sync.orphanedSynced'),
        description: t('sync.registeredOrphaned', {
          count: result.registered_videos,
          files: result.scanned_files,
        }),
      });

      pagination.refreshVideos(filters.buildSearchParams());
      pagination.loadStats();
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

  // Video actions
  const handleDownload = useCallback(
    (video: Video) => {
      const link = document.createElement('a');
      const downloadUrl =
        video.download_url || `/api/download?path=${encodeURIComponent(video.file_path || '')}`;
      link.href = `${API_BASE}${downloadUrl}`;
      link.download = video.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast({
        title: t('downloadStarted'),
        description: t('downloading', { filename: video.filename }),
      });
    },
    [toast, t]
  );

  const handleMarkPosted = useCallback(
    async (video: Video) => {
      try {
        const response = await api.post(`/api/videos/managed/${video.id}/mark-posted`);

        if (!response.ok) {
          throw new Error('Failed to mark video as posted');
        }

        toast({
          title: t('videoMarkedPosted'),
          description: t('markedAsPosted', { filename: video.filename }),
        });

        pagination.setVideos((prev) =>
          prev.map((v) =>
            v.id === video.id ? { ...v, posted: true, posted_at: new Date().toISOString() } : v
          )
        );
        pagination.loadStats();
      } catch {
        toast({
          title: t('error'),
          description: t('failedToMark'),
          variant: 'destructive',
        });
      }
    },
    [toast, t, pagination]
  );

  // Delete handlers
  const handleDeleteClick = useCallback((video: Video) => {
    setVideoToDelete(video);
    setDeleteDialogOpen(true);
  }, []);

  const handleDeleteConfirm = async () => {
    if (!videoToDelete) return;

    try {
      const response = await api.delete(
        `/api/videos/managed/${videoToDelete.id}?delete_file=true`
      );

      if (!response.ok) {
        throw new Error('Failed to delete video');
      }

      toast({
        title: t('videoDeleted'),
        description: t('permanentlyDeleted', { filename: videoToDelete.filename }),
      });

      pagination.setVideos((prev) => prev.filter((v) => v.id !== videoToDelete.id));
      selection.removeFromSelection(videoToDelete.id);
      pagination.loadStats();
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

  const handleBulkDeleteConfirm = async () => {
    const selected = filteredVideos.filter((v) => selection.selectedVideos.has(v.id));
    const selectedCount = selected.length;

    try {
      await Promise.all(
        selected.map(async (video) => {
          const response = await api.delete(
            `/api/videos/managed/${video.id}?delete_file=true`
          );
          if (!response.ok) {
            throw new Error(`Failed to delete ${video.filename}`);
          }
        })
      );

      pagination.setVideos((prev) => prev.filter((v) => !selection.selectedVideos.has(v.id)));
      selection.clearSelection();

      toast({
        title: t('videosDeleted'),
        description: t('successfullyDeleted', {
          count: selectedCount,
          plural: selectedCount !== 1 ? 's' : '',
        }),
      });

      pagination.loadStats();
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

  // Initial load effect — re-fetch when any filter changes (including search)
  useEffect(() => {
    const initialLoad = async () => {
      const params = filters.buildSearchParams(0);
      await Promise.all([
        pagination.refreshVideos(params),
        pagination.loadStats(),
      ]);
    };

    initialLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.workflowFilter, filters.postedFilter, filters.sortBy, filters.sortOrder, filters.debouncedSearchTerm]);

  // Videos are now filtered server-side; use them directly
  const filteredVideos = pagination.videos;

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <PlaySquare className="h-8 w-8 text-muted-foreground" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground text-lg">
            Manage and organize your generated videos
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSyncPanel(!showSyncPanel)}
            className="h-10 border-dashed"
          >
            <Settings2 className="mr-2 h-4 w-4" />
            {showSyncPanel ? t('hideSync') : t('showSync')}
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => pagination.refreshVideos(filters.buildSearchParams())}
            disabled={pagination.loading}
            className="h-10 w-10"
          >
            <RefreshCw className={`h-4 w-4 ${pagination.loading ? 'animate-spin' : ''}`} />
          </Button>
          {/* View Toggle */}
          <div className="flex bg-muted rounded-lg p-1">
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => handleViewModeChange('grid')}
              className="h-8 px-2 rounded-md transition-all"
            >
              <LayoutGrid className="size-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => handleViewModeChange('list')}
              className="h-8 px-2 rounded-md transition-all"
            >
              <List className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-8">
        {/* Stats */}
        <VideoStats stats={pagination.stats} loading={pagination.loading && !pagination.stats} />

        {/* Sync Panel */}
        {showSyncPanel && (
          <div className="animate-in fade-in slide-in-from-top-4 duration-300">
            <SyncPanel
              onSyncFromJobs={syncVideosFromJobs}
              onSyncOrphaned={syncOrphanedVideos}
              syncing={syncing}
            />
          </div>
        )}

        <Separator />

        {/* Filters */}
        <VideoFilters
          searchTerm={filters.searchTerm}
          onSearchChange={filters.setSearchTerm}
          workflowFilter={filters.workflowFilter}
          onWorkflowFilterChange={filters.setWorkflowFilter}
          postedFilter={filters.postedFilter}
          onPostedFilterChange={filters.setPostedFilter}
          sortBy={filters.sortBy}
          onSortByChange={filters.setSortBy}
          sortOrder={filters.sortOrder}
          onSortOrderChange={filters.setSortOrder}
        />

        {/* Selection Info */}
        {selection.selectedVideos.size > 0 && (
          <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 flex items-center justify-between animate-in fade-in duration-300">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="bg-primary/20 text-primary hover:bg-primary/30">
                {selection.selectedVideos.size} Selected
              </Badge>
              <span className="text-sm text-muted-foreground">{t('selected')}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={selection.handleClearSelection}
              className="h-8 text-xs"
            >
              Clear Selection
            </Button>
          </div>
        )}

        {/* Videos Grid/List */}
        <VideoGrid
          videos={filteredVideos}
          loading={pagination.loading}
          loadingMore={pagination.loadingMore}
          hasMore={pagination.hasMore}
          searchTerm={filters.searchTerm}
          viewMode={viewMode}
          selectedVideos={selection.selectedVideos}
          onDownload={handleDownload}
          onPlay={setPreviewVideo}
          onMarkPosted={handleMarkPosted}
          onDelete={handleDeleteClick}
          onSelect={selection.handleVideoSelect}
          onLoadMore={() => pagination.loadMoreVideos(filters.buildSearchParams())}
        />
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
      <VideoBulkActions
        filteredVideos={filteredVideos}
        selectedVideos={selection.selectedVideos}
        onClearSelection={selection.handleClearSelection}
        onSetVideos={pagination.setVideos}
        onLoadStats={pagination.loadStats}
        onOpenBulkDeleteDialog={() => setBulkDeleteDialogOpen(true)}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('dialog.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t.rich('dialog.deleteDescription', {
                filename: videoToDelete?.filename || '',
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
              <br />
              <br />
              {t('dialog.deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('dialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
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
                count: selection.selectedVideos.size,
                plural: selection.selectedVideos.size !== 1 ? 's' : '',
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
              <br />
              <br />
              {t('dialog.deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('dialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t('dialog.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
