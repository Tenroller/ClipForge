'use client';

import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Play, Film, Brain, Video, Check, Clock, Trash2, TrendingUp, Tag, Star } from "lucide-react";
import Image from 'next/image';
import { getThumbnailUrl } from '@/lib/api';
import { formatDuration } from '@/utils/formatDuration';

export interface VideoMetadata {
  title?: string;
  clip_index?: number;
  start_time?: number;
  end_time?: number;
  optimized_start?: number;
  optimized_end?: number;
  cut_padding_before?: number;
  cut_padding_after?: number;
  hook?: string;
  reason?: string;
  caption?: string;
  subtitles?: string;
  notes?: string;
  viral_score?: number;
  confidence?: number;
  engagement_factors?: Record<string, any>;
  tags?: string[];
  thumbnail_text?: string;
  recommended_crop?: string;
}

export interface Video {
  id: string;
  job_id: string;
  workflow: 'moneyprinter' | 'brainrot' | 'podcastclips';
  filename: string;
  file_path?: string;
  size_bytes: number;
  created_at: string;
  duration_seconds?: number;
  download_url: string;
  thumbnail_url?: string;
  posted?: boolean;
  posted_at?: string;
  metadata?: VideoMetadata;
}

interface VideoCardProps {
  video: Video;
  onDownload: (video: Video) => void;
  onPlay?: (video: Video) => void;
  onMarkPosted?: (video: Video) => void;
  onDelete?: (video: Video) => void;
  selected?: boolean;
  onSelect?: (video: Video, selected: boolean) => void;
}

export default function VideoCard({ video, onDownload, onPlay, onMarkPosted, onDelete, selected = false, onSelect }: VideoCardProps) {
  const t = useTranslations('videoCard');
  
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getWorkflowIcon = () => {
    switch (video.workflow) {
      case 'moneyprinter':
        return <Film className="size-4" />;
      case 'brainrot':
        return <Brain className="size-4" />;
      case 'podcastclips':
        return <Video className="size-4" />;
      default:
        return <Video className="size-4" />;
    }
  };

  return (
    <Card className={`hover:shadow-lg transition-shadow ${selected ? 'ring-2 ring-primary' : ''}`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          {/* Thumbnail */}
          <div className="relative w-32 h-20 bg-muted rounded-lg overflow-hidden shrink-0 group">
            {/* Selection Checkbox */}
            {onSelect && (
              <div className="absolute top-1 left-1 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                <Checkbox
                  checked={selected}
                  onCheckedChange={(checked) => onSelect(video, checked as boolean)}
                  className="bg-white/90 border-2"
                />
              </div>
            )}
            {video.thumbnail_url ? (
              <Image
                src={getThumbnailUrl(video.thumbnail_url)}
                alt={video.filename}
                fill
                sizes="128px"
                className="object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Video className="size-8 text-muted-foreground" />
              </div>
            )}
            {video.duration_seconds && (
              <div className="absolute bottom-1 right-1 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded">
                {formatDuration(video.duration_seconds)}
              </div>
            )}
          </div>

          {/* Details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium truncate" title={video.metadata?.title || video.filename}>
                  {video.metadata?.title || video.filename}
                </h3>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <Badge variant="outline" className="text-xs">
                    {getWorkflowIcon()}
                    <span className="ml-1">{video.workflow}</span>
                  </Badge>
                  {video.posted && (
                    <Badge variant="default" className="text-xs">
                      <Check className="size-3 mr-1" />
                      {t('posted')}
                    </Badge>
                  )}
                  {/* Viral Score Badge */}
                  {video.metadata?.viral_score !== undefined && video.metadata.viral_score > 0 && (
                    <Badge
                      variant={video.metadata.viral_score >= 90 ? "default" : video.metadata.viral_score >= 80 ? "secondary" : "outline"}
                      className="text-xs"
                    >
                      <TrendingUp className="size-3 mr-1" />
                      {video.metadata.viral_score}
                    </Badge>
                  )}
                  {/* Confidence Badge */}
                  {video.metadata?.confidence !== undefined && video.metadata.confidence > 0 && (
                    <Badge variant="outline" className="text-xs">
                      <Star className="size-3 mr-1" />
                      {Math.round(video.metadata.confidence * 100)}%
                    </Badge>
                  )}
                </div>
                {/* Tags */}
                {video.metadata?.tags && video.metadata.tags.length > 0 && (
                  <div className="flex items-center gap-1 mt-2 flex-wrap">
                    {video.metadata.tags.slice(0, 3).map((tag, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        <Tag className="size-2 mr-1" />
                        {tag}
                      </Badge>
                    ))}
                    {video.metadata.tags.length > 3 && (
                      <span className="text-xs text-muted-foreground">
                        +{video.metadata.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-3">
              <div className="flex items-center gap-1">
                <Clock className="size-3" />
                {formatDate(video.created_at)}
              </div>
              <div>
                {t('size')} {formatFileSize(video.size_bytes)}
              </div>
              {video.metadata?.hook ? (
                <div className="col-span-2 truncate italic text-xs">
                  "{video.metadata.hook}"
                </div>
              ) : (
                <div className="col-span-2 truncate">
                  {t('job')} {video.job_id.substring(0, 16)}...
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {onPlay && (
                <Button variant="outline" size="sm" onClick={() => onPlay(video)}>
                  <Play className="size-3 mr-1" />
                  {t('play')}
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => onDownload(video)}>
                <Download className="size-3 mr-1" />
                {t('download')}
              </Button>
              {onMarkPosted && !video.posted && (
                <Button variant="outline" size="sm" onClick={() => onMarkPosted(video)}>
                  <Check className="size-3 mr-1" />
                  {t('markPosted')}
                </Button>
              )}
              {onDelete && (
                <Button variant="outline" size="sm" onClick={() => onDelete(video)} className="text-destructive hover:text-destructive">
                  <Trash2 className="size-3 mr-1" />
                  {t('delete')}
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
