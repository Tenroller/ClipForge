'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Download, Check, Film, Brain, Video as VideoIcon, Clock, Database } from "lucide-react";
import type { Video } from './VideoCard';
import { API_BASE } from '@/lib/api';
import { getWorkflowClasses } from '@/lib/status';

interface VideoPreviewModalProps {
  video: Video | null;
  open: boolean;
  onClose: () => void;
  onDownload: (video: Video) => void;
  onMarkPosted?: (video: Video) => void;
}

export default function VideoPreviewModal({
  video,
  open,
  onClose,
  onDownload,
  onMarkPosted
}: VideoPreviewModalProps) {
  if (!video) return null;

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
      month: 'long',
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
        return <VideoIcon className="size-4" />;
      default:
        return <VideoIcon className="size-4" />;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl flex items-center gap-2">
            {video.filename}
          </DialogTitle>
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="outline" className={getWorkflowClasses(video.workflow)}>
              {getWorkflowIcon()}
              <span className="ml-1 capitalize">{video.workflow}</span>
            </Badge>
            {video.posted && (
              <Badge variant="default" className="bg-success">
                <Check className="size-3 mr-1" />
                Posted
              </Badge>
            )}
          </div>
        </DialogHeader>

        {/* Video Player */}
        <div className="w-full bg-black rounded-lg overflow-hidden">
          <video
            controls
            className="w-full h-auto max-h-[60vh]"
            preload="metadata"
            src={`${API_BASE}${video.download_url}`}
          >
            Your browser does not support the video tag.
          </video>
        </div>

        {/* Video Details */}
        <div className="space-y-4 pt-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="size-4" />
                <span className="font-medium">Created:</span>
              </div>
              <div className="pl-6">{formatDate(video.created_at)}</div>
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Database className="size-4" />
                <span className="font-medium">Size:</span>
              </div>
              <div className="pl-6">{formatFileSize(video.size_bytes)}</div>
            </div>

            {video.duration_seconds && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <VideoIcon className="size-4" />
                  <span className="font-medium">Duration:</span>
                </div>
                <div className="pl-6">
                  {Math.floor(video.duration_seconds / 60)}:{(video.duration_seconds % 60).toString().padStart(2, '0')}
                </div>
              </div>
            )}

            <div className="space-y-1">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Film className="size-4" />
                <span className="font-medium">Job ID:</span>
              </div>
              <div className="pl-6 truncate" title={video.job_id}>
                {video.job_id}
              </div>
            </div>

            {video.posted_at && (
              <div className="space-y-1 col-span-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Check className="size-4" />
                  <span className="font-medium">Posted At:</span>
                </div>
                <div className="pl-6">{formatDate(video.posted_at)}</div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t">
            <Button
              onClick={() => {
                onDownload(video);
                onClose();
              }}
              className="flex-1"
            >
              <Download className="size-4 mr-2" />
              Download Video
            </Button>
            {onMarkPosted && !video.posted && (
              <Button
                variant="outline"
                onClick={() => {
                  onMarkPosted(video);
                  onClose();
                }}
              >
                <Check className="size-4 mr-2" />
                Mark as Posted
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
