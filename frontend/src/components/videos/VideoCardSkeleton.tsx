'use client';

import { Card, CardContent } from '@/components/ui/card';

interface VideoCardSkeletonProps {
  variant?: 'grid' | 'list';
}

export default function VideoCardSkeleton({ variant = 'grid' }: VideoCardSkeletonProps) {
  if (variant === 'list') {
    return (
      <Card className="animate-pulse">
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            {/* Thumbnail skeleton */}
            <div className="relative w-32 h-20 bg-muted rounded-lg shrink-0" />

            {/* Details skeleton */}
            <div className="flex-1 min-w-0 space-y-3">
              <div className="space-y-2">
                <div className="h-5 bg-muted rounded w-3/4" />
                <div className="flex items-center gap-2">
                  <div className="h-6 bg-muted rounded w-24" />
                  <div className="h-6 bg-muted rounded w-16" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="h-4 bg-muted rounded" />
                <div className="h-4 bg-muted rounded" />
                <div className="h-4 bg-muted rounded col-span-2" />
              </div>

              <div className="flex gap-2">
                <div className="h-8 bg-muted rounded w-20" />
                <div className="h-8 bg-muted rounded w-24" />
                <div className="h-8 bg-muted rounded w-28" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Grid variant
  return (
    <Card className="animate-pulse overflow-hidden">
      <CardContent className="p-0">
        {/* Thumbnail skeleton - 9:16 aspect ratio */}
        <div className="relative w-full aspect-[9/16] bg-muted" />

        {/* Content skeleton */}
        <div className="p-3 space-y-3">
          {/* Title skeleton */}
          <div className="space-y-2">
            <div className="h-4 bg-muted rounded w-full" />
            <div className="h-4 bg-muted rounded w-4/5" />
          </div>

          {/* Badge skeleton */}
          <div className="h-6 bg-muted rounded w-24" />

          {/* Metadata skeleton */}
          <div className="space-y-1.5">
            <div className="h-3 bg-muted rounded w-32" />
            <div className="h-3 bg-muted rounded w-20" />
          </div>

          {/* Actions skeleton */}
          <div className="flex gap-2 pt-1">
            <div className="h-8 bg-muted rounded flex-1" />
            <div className="h-8 bg-muted rounded w-8" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
