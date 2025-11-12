'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Play, Film, Brain, Video, Check, Clock, Trash2 } from "lucide-react";
import Image from 'next/image';
import { getThumbnailUrl } from '@/lib/api';
import { formatDuration } from '@/utils/formatDuration';

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
                <h3 className="font-medium truncate" title={video.filename}>
                  {video.filename}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="text-xs">
                    {getWorkflowIcon()}
                    <span className="ml-1">{video.workflow}</span>
                  </Badge>
                  {video.posted && (
                    <Badge variant="default" className="text-xs">
                      <Check className="size-3 mr-1" />
                      Posted
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-3">
              <div className="flex items-center gap-1">
                <Clock className="size-3" />
                {formatDate(video.created_at)}
              </div>
              <div>
                Size: {formatFileSize(video.size_bytes)}
              </div>
              <div className="col-span-2 truncate">
                Job: {video.job_id.substring(0, 16)}...
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {onPlay && (
                <Button variant="outline" size="sm" onClick={() => onPlay(video)}>
                  <Play className="size-3 mr-1" />
                  Play
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => onDownload(video)}>
                <Download className="size-3 mr-1" />
                Download
              </Button>
              {onMarkPosted && !video.posted && (
                <Button variant="outline" size="sm" onClick={() => onMarkPosted(video)}>
                  <Check className="size-3 mr-1" />
                  Mark Posted
                </Button>
              )}
              {onDelete && (
                <Button variant="outline" size="sm" onClick={() => onDelete(video)} className="text-destructive hover:text-destructive">
                  <Trash2 className="size-3 mr-1" />
                  Delete
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
