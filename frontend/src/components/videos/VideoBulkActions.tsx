'use client';

import React, { useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { useToast } from '@/hooks/use-toast';
import { type Video } from '@/components/videos/VideoCard';
import BulkActionsBar from '@/components/videos/BulkActionsBar';
import { api, API_BASE } from '@/lib/api';

interface VideoBulkActionsProps {
  filteredVideos: Video[];
  selectedVideos: Set<string>;
  onClearSelection: () => void;
  onSetVideos: React.Dispatch<React.SetStateAction<Video[]>>;
  onLoadStats: () => void;
  onOpenBulkDeleteDialog: () => void;
}

export default function VideoBulkActions({
  filteredVideos,
  selectedVideos,
  onClearSelection,
  onSetVideos,
  onLoadStats,
  onOpenBulkDeleteDialog,
}: VideoBulkActionsProps) {
  const { toast } = useToast();
  const t = useTranslations('videos');

  const handleDownload = useCallback(
    (video: Video) => {
      const link = document.createElement('a');
      const downloadUrl =
        video.download_url ||
        `/api/download?path=${encodeURIComponent(video.file_path || '')}`;
      link.href = `${API_BASE}${downloadUrl}`;
      link.download = video.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    []
  );

  const handleBulkDownload = useCallback(() => {
    const selected = filteredVideos.filter((v) => selectedVideos.has(v.id));
    selected.forEach((video) => handleDownload(video));
    toast({
      title: t('bulkDownloadStarted'),
      description: t('downloadingMultiple', { count: selected.length }),
    });
  }, [filteredVideos, selectedVideos, handleDownload, toast, t]);

  const handleBulkMarkPosted = useCallback(async () => {
    const selected = filteredVideos.filter(
      (v) => selectedVideos.has(v.id) && !v.posted
    );

    try {
      await Promise.all(
        selected.map(async (video) => {
          const response = await api.post(
            `/api/videos/managed/${video.id}/mark-posted`
          );
          if (!response.ok) {
            throw new Error('Failed to mark video as posted');
          }
        })
      );

      // Update local state
      onSetVideos((prev) =>
        prev.map((v) =>
          selectedVideos.has(v.id) && !v.posted
            ? { ...v, posted: true, posted_at: new Date().toISOString() }
            : v
        )
      );

      onClearSelection();
      onLoadStats();

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
  }, [filteredVideos, selectedVideos, onSetVideos, onClearSelection, onLoadStats, toast, t]);

  // Count selected unposted videos
  const selectedUnpostedCount = filteredVideos.filter(
    (v) => selectedVideos.has(v.id) && !v.posted
  ).length;

  return (
    <BulkActionsBar
      selectedCount={selectedVideos.size}
      onDownloadAll={handleBulkDownload}
      onMarkAllPosted={handleBulkMarkPosted}
      onDeleteAll={onOpenBulkDeleteDialog}
      onClearSelection={onClearSelection}
      totalUnposted={selectedUnpostedCount}
    />
  );
}
