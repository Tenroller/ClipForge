'use client';

import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Play, Film, Brain, Video as VideoIcon, Check, Clock, Trash2, TrendingUp, Tag, Star } from "lucide-react";
import { useState } from 'react';
import Image from 'next/image';
import { getThumbnailUrl } from '@/lib/api';
import { formatDuration } from '@/utils/formatDuration';
import { Video, VideoMetadata } from './VideoCard';

interface GridVideoCardProps {
  video: Video;
  onDownload: (video: Video) => void;
  onPlay?: (video: Video) => void;
  onMarkPosted?: (video: Video) => void;
  onDelete?: (video: Video) => void;
  selected?: boolean;
  onSelect?: (video: Video, selected: boolean) => void;
}

export default function GridVideoCard({
  video,
  onDownload,
  onPlay,
  onMarkPosted,
  onDelete,
  selected = false,
  onSelect
}: GridVideoCardProps) {
  const t = useTranslations('videoCard');
  const [imageLoaded, setImageLoaded] = useState(false);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getWorkflowIcon = () => {
    switch (video.workflow) {
      case 'moneyprinter':
        return <Film className="size-3" />;
      case 'brainrot':
        return <Brain className="size-3" />;
      case 'podcastclips':
        return <VideoIcon className="size-3" />;
      default:
        return <VideoIcon className="size-3" />;
    }
  };

  const getWorkflowColor = () => {
    switch (video.workflow) {
      case 'moneyprinter':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'brainrot':
        return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
      case 'podcastclips':
        return 'bg-green-500/10 text-green-500 border-green-500/20';
      default:
        return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
    }
  };

  return (
    <Card className={`group overflow-hidden transition-all duration-300 rounded-2xl border-2 shadow-lg hover:shadow-2xl hover:border-primary/60 hover:-translate-y-1 bg-gradient-to-br from-card/90 to-card/50 backdrop-blur-md ${selected ? 'ring-4 ring-primary ring-offset-2 ring-offset-background' : ''}`}>
      <CardContent className="p-0">
        {/* Thumbnail Section - 9:16 Portrait */}
        <div className="relative w-full aspect-[9/16] bg-gradient-to-br from-muted/80 to-muted overflow-hidden rounded-t-2xl">
          {/* Selection Checkbox */}
          {onSelect && (
            <div className="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
              <Checkbox
                checked={selected}
                onCheckedChange={(checked) => onSelect(video, checked as boolean)}
                className="bg-white/90 border-2"
              />
            </div>
          )}

          {/* Thumbnail Image */}
          {video.thumbnail_url ? (
            <>
              {!imageLoaded && (
                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-muted/80 to-muted animate-pulse">
                  <VideoIcon className="size-16 text-muted-foreground/40" />
                </div>
              )}
              <Image
                src={getThumbnailUrl(video.thumbnail_url)}
                alt={video.filename}
                fill
                sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
                className={`object-cover transition-all duration-500 group-hover:scale-110 group-hover:brightness-110 ${
                  imageLoaded ? 'opacity-100' : 'opacity-0'
                }`}
                onLoad={() => setImageLoaded(true)}
              />
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-muted/60 to-muted/80">
              <VideoIcon className="size-16 text-muted-foreground/50" />
            </div>
          )}

          {/* Play Button Overlay */}
          {onPlay && (
            <div
              className="absolute inset-0 flex items-center justify-center bg-gradient-to-t from-black/70 via-black/40 to-black/20 opacity-0 group-hover:opacity-100 transition-all duration-300 cursor-pointer backdrop-blur-[2px]"
              onClick={() => onPlay(video)}
            >
              <div className="w-16 h-16 rounded-full bg-white/95 flex items-center justify-center transform transition-all duration-300 hover:scale-125 hover:bg-white shadow-2xl ring-4 ring-white/20">
                <Play className="size-6 text-gray-900 ml-1" fill="currentColor" />
              </div>
            </div>
          )}

          {/* Duration Badge */}
          {video.duration_seconds && (
            <div className="absolute bottom-2 right-2 bg-black/95 backdrop-blur-md text-white text-xs px-2.5 py-1.5 rounded-lg font-semibold shadow-lg border border-white/10">
              {formatDuration(video.duration_seconds)}
            </div>
          )}

          {/* Posted Badge */}
          {video.posted && (
            <div className="absolute top-2 right-2">
              <Badge variant="default" className="text-xs bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-lg border border-green-500/30">
                <Check className="size-3 mr-1" />
                {t('posted')}
              </Badge>
            </div>
          )}
        </div>

        {/* Content Section */}
        <div className="p-5 space-y-4">
          {/* Title and Workflow Badge */}
          <div className="space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-bold text-sm line-clamp-2 leading-snug flex-1 group-hover:text-primary transition-colors" title={video.metadata?.title || video.filename}>
                {video.metadata?.title || video.filename}
              </h3>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className={`text-xs w-fit font-semibold shadow-sm ${getWorkflowColor()}`}>
                {getWorkflowIcon()}
                <span className="ml-1.5 capitalize">{video.workflow}</span>
              </Badge>
              {/* Viral Score Badge */}
              {video.metadata?.viral_score !== undefined && video.metadata.viral_score > 0 && (
                <Badge
                  variant={video.metadata.viral_score >= 90 ? "default" : video.metadata.viral_score >= 80 ? "secondary" : "outline"}
                  className={`text-xs font-semibold shadow-sm ${
                    video.metadata.viral_score >= 90
                      ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white border-orange-400/30'
                      : video.metadata.viral_score >= 80
                      ? 'bg-gradient-to-r from-yellow-400 to-orange-400 text-white border-yellow-400/30'
                      : ''
                  }`}
                >
                  <TrendingUp className="size-3 mr-1" />
                  {video.metadata.viral_score}
                </Badge>
              )}
              {/* Confidence Badge */}
              {video.metadata?.confidence !== undefined && video.metadata.confidence > 0 && (
                <Badge variant="outline" className="text-xs font-semibold shadow-sm bg-amber-500/10 text-amber-600 border-amber-500/20">
                  <Star className="size-3 mr-1" />
                  {Math.round(video.metadata.confidence * 100)}%
                </Badge>
              )}
            </div>
          </div>

          {/* Tags */}
          {video.metadata?.tags && video.metadata.tags.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {video.metadata.tags.slice(0, 2).map((tag, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs font-medium shadow-sm bg-secondary/60 hover:bg-secondary/80 transition-colors">
                  <Tag className="size-2.5 mr-1" />
                  {tag}
                </Badge>
              ))}
              {video.metadata.tags.length > 2 && (
                <span className="text-xs text-muted-foreground font-medium">
                  +{video.metadata.tags.length - 2}
                </span>
              )}
            </div>
          )}

          {/* Metadata */}
          <div className="flex items-center justify-between text-xs text-muted-foreground/80">
            <div className="flex items-center gap-2">
              <Clock className="size-3.5 shrink-0" />
              <span className="font-medium">{formatDate(video.created_at)}</span>
            </div>
            <span className="font-bold text-foreground/70">{formatFileSize(video.size_bytes)}</span>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDownload(video)}
              className="flex-1 h-10 font-semibold shadow-sm hover:shadow-md hover:border-primary/50 hover:bg-primary/5 transition-all"
            >
              <Download className="size-4 mr-2" />
              {t('download')}
            </Button>
            {onMarkPosted && !video.posted && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onMarkPosted(video)}
                className="h-10 px-3.5 shadow-sm hover:shadow-md hover:border-green-500/50 hover:bg-green-500/5 transition-all"
                title={t('markAsPosted')}
              >
                <Check className="size-4" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDelete(video)}
                className="h-10 px-3.5 text-destructive hover:text-destructive shadow-sm hover:shadow-md hover:border-destructive/50 hover:bg-destructive/5 transition-all"
                title={t('deleteVideo')}
              >
                <Trash2 className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
