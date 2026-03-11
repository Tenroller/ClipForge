import { useState, useCallback } from 'react';
import { type Video } from '@/components/videos/VideoCard';

export interface UseVideoSelectionReturn {
  selectedVideos: Set<string>;
  handleVideoSelect: (video: Video, selected: boolean) => void;
  handleClearSelection: () => void;
  removeFromSelection: (videoId: string) => void;
  clearSelection: () => void;
}

export function useVideoSelection(): UseVideoSelectionReturn {
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());

  const handleVideoSelect = useCallback((video: Video, selected: boolean) => {
    setSelectedVideos((prev) => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(video.id);
      } else {
        newSet.delete(video.id);
      }
      return newSet;
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedVideos(new Set());
  }, []);

  const removeFromSelection = useCallback((videoId: string) => {
    setSelectedVideos((prev) => {
      const newSet = new Set(prev);
      newSet.delete(videoId);
      return newSet;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedVideos(new Set());
  }, []);

  return {
    selectedVideos,
    handleVideoSelect,
    handleClearSelection,
    removeFromSelection,
    clearSelection,
  };
}
