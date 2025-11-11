'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Play, Film, Brain, Video as VideoIcon, Check, Clock } from "lucide-react";
import { useState } from 'react';
import Image from 'next/image';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

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

interface GridVideoCardProps {
  video: Video;
  onDownload: (video: Video) => void;
  onPlay?: (video: Video) => void;
  onMarkPosted?: (video: Video) => void;
  selected?: boolean;
  onSelect?: (video: Video, selected: boolean) => void;
}

export default function GridVideoCard({
  video,
  onDownload,
  onPlay,
  onMarkPosted,
  selected = false,
  onSelect
}: GridVideoCardProps) {
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
    <Card className={`group overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 ${selected ? 'ring-2 ring-primary' : ''}`}>
      <CardContent className="p-0">
        {/* Thumbnail Section - 9:16 Portrait */}
        <div className="relative w-full aspect-[9/16] bg-muted overflow-hidden">
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
                <div className="absolute inset-0 flex items-center justify-center bg-muted animate-pulse">
                  <VideoIcon className="size-12 text-muted-foreground" />
                </div>
              )}
              <Image
                src={`${API_BASE}${video.thumbnail_url}`}
                alt={video.filename}
                fill
                sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
                className={`object-cover transition-all duration-300 group-hover:scale-105 ${
                  imageLoaded ? 'opacity-100' : 'opacity-0'
                }`}
                onLoad={() => setImageLoaded(true)}
              />
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <VideoIcon className="size-12 text-muted-foreground" />
            </div>
          )}

          {/* Play Button Overlay */}
          {onPlay && (
            <div
              className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
              onClick={() => onPlay(video)}
            >
              <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center transform transition-transform group-hover:scale-110">
                <Play className="size-6 text-gray-900 ml-1" />
              </div>
            </div>
          )}

          {/* Duration Badge */}
          {video.duration_seconds && (
            <div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded font-medium">
              {Math.floor(video.duration_seconds / 60)}:{(video.duration_seconds % 60).toString().padStart(2, '0')}
            </div>
          )}

          {/* Posted Badge */}
          {video.posted && (
            <div className="absolute top-2 right-2">
              <Badge variant="default" className="text-xs bg-green-600 hover:bg-green-700">
                <Check className="size-3 mr-1" />
                Posted
              </Badge>
            </div>
          )}
        </div>

        {/* Content Section */}
        <div className="p-3 space-y-3">
          {/* Title */}
          <div>
            <h3 className="font-medium text-sm line-clamp-2 leading-tight min-h-[2.5rem]" title={video.filename}>
              {video.filename}
            </h3>
          </div>

          {/* Workflow Badge */}
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={`text-xs ${getWorkflowColor()}`}>
              {getWorkflowIcon()}
              <span className="ml-1 capitalize">{video.workflow}</span>
            </Badge>
          </div>

          {/* Metadata */}
          <div className="space-y-1 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Clock className="size-3 shrink-0" />
              <span>{formatDate(video.created_at)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Size: {formatFileSize(video.size_bytes)}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDownload(video)}
              className="flex-1 h-8 text-xs"
            >
              <Download className="size-3 mr-1" />
              Download
            </Button>
            {onMarkPosted && !video.posted && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onMarkPosted(video)}
                className="h-8 text-xs"
                title="Mark as Posted"
              >
                <Check className="size-3" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
