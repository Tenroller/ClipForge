'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import VideoCard, { type Video } from '@/components/videos/VideoCard';
import GridVideoCard from '@/components/videos/GridVideoCard';
import VideoCardSkeleton from '@/components/videos/VideoCardSkeleton';
import { ChevronDown, Loader2, Film } from 'lucide-react';

interface VideoGridProps {
  videos: Video[];
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  searchTerm: string;
  viewMode: 'grid' | 'list';
  selectedVideos: Set<string>;
  onDownload: (video: Video) => void;
  onPlay: (video: Video) => void;
  onMarkPosted: (video: Video) => void;
  onDelete: (video: Video) => void;
  onSelect: (video: Video, selected: boolean) => void;
  onLoadMore: () => void;
}

export default function VideoGrid({
  videos,
  loading,
  loadingMore,
  hasMore,
  searchTerm,
  viewMode,
  selectedVideos,
  onDownload,
  onPlay,
  onMarkPosted,
  onDelete,
  onSelect,
  onLoadMore,
}: VideoGridProps) {
  const t = useTranslations('videos');

  if (loading) {
    return viewMode === 'grid' ? (
      <div className="grid grid-cols-1 min-[400px]:grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <VideoCardSkeleton key={i} variant="grid" />
        ))}
      </div>
    ) : (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <VideoCardSkeleton key={i} variant="list" />
        ))}
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <Card className="border-border/50 bg-muted/10 border-dashed">
        <CardContent className="pt-6">
          <EmptyState
            icon={Film}
            title={t('noVideos')}
            description={searchTerm ? t('tryAdjusting') : t('generateToSee')}
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 min-[400px]:grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
          {videos.map((video) => (
            <GridVideoCard
              key={video.id}
              video={video}
              onDownload={onDownload}
              onPlay={onPlay}
              onMarkPosted={onMarkPosted}
              onDelete={onDelete}
              selected={selectedVideos.has(video.id)}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onDownload={onDownload}
              onPlay={onPlay}
              onMarkPosted={onMarkPosted}
              onDelete={onDelete}
              selected={selectedVideos.has(video.id)}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}

      {/* Load More Button */}
      {hasMore && (
        <div className="flex justify-center pt-8 pb-4">
          <Button
            variant="outline"
            size="lg"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="rounded-md px-8"
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
      {loadingMore &&
        (viewMode === 'grid' ? (
          <div className="grid grid-cols-1 min-[400px]:grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 mt-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <VideoCardSkeleton key={i} variant="grid" />
            ))}
          </div>
        ) : (
          <div className="space-y-4 mt-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <VideoCardSkeleton key={i} variant="list" />
            ))}
          </div>
        ))}
    </>
  );
}
