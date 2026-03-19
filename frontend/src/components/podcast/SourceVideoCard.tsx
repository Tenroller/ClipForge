'use client';

import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Clock, Download, ExternalLink, Trash2 } from 'lucide-react';
import type { PodcastProject } from '@/lib/api';

interface SourceVideoCardProps {
  project: PodcastProject;
  onClick: () => void;
  onOpenExternal?: () => void;
  onDelete?: () => void;
  onDownloadTranscript?: () => void;
}

export default function SourceVideoCard({
  project,
  onClick,
  onOpenExternal,
  onDelete,
  onDownloadTranscript,
}: SourceVideoCardProps) {
  const t = useTranslations('sourceVideoCard');

  // Format date to DD/MM/YY
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  };

  // Get status badge color and text
  const getStatusBadge = () => {
    switch (project.status) {
      case 'analysis_complete':
        return { color: 'bg-success', text: t('analysisComplete') };
      case 'active':
        return { color: 'bg-info', text: t('active') };
      case 'expired':
        return { color: 'bg-warning', text: t('expired') };
      case 'error':
        return { color: 'bg-destructive', text: t('error') };
      default:
        return { color: 'bg-muted-foreground', text: project.status };
    }
  };

  const statusBadge = getStatusBadge();

  return (
    <Card
      className="group relative overflow-hidden rounded-2xl bg-card border cursor-pointer"
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      role="button"
      aria-label={project.title}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-muted">
        {project.thumbnail_url ? (
          <Image
            src={project.thumbnail_url}
            alt={project.title}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-muted">
            <span className="text-4xl text-muted-foreground/50">?</span>
          </div>
        )}

        {/* Status Badge */}
        <div className="absolute top-3 left-3">
          <Badge className={`${statusBadge.color} text-white border-0 text-xs font-medium px-2 py-0.5`}>
            {statusBadge.text}
          </Badge>
        </div>

        {/* Action Buttons */}
        <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
          {onOpenExternal && (
            <Button
              variant="secondary"
              size="icon"
              className="h-8 w-8 bg-black/60 hover:bg-black/80 border-0"
              aria-label={t('openYoutube')}
              onClick={(e) => {
                e.stopPropagation();
                onOpenExternal();
              }}
            >
              <ExternalLink className="h-4 w-4 text-white" />
            </Button>
          )}
          {onDelete && (
            <Button
              variant="secondary"
              size="icon"
              className="h-8 w-8 bg-black/60 hover:bg-destructive/80 border-0"
              aria-label={t('deleteProject')}
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
            >
              <Trash2 className="h-4 w-4 text-white" />
            </Button>
          )}
        </div>

        {/* Format Badges */}
        <div className="absolute bottom-3 left-3 flex gap-1.5">
          <Badge className="bg-accent text-accent-foreground border-0 text-xs font-bold px-2 py-0.5">
            {project.format_options.aspect_ratio}
          </Badge>
          <Badge className="bg-warning text-warning-foreground border-0 text-xs font-bold px-2 py-0.5">
            {project.format_options.mode}
          </Badge>
          <Badge className="bg-info text-info-foreground border-0 text-xs font-bold px-2 py-0.5">
            {project.format_options.face_tracking ? t('face') : t('single')}
          </Badge>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Title */}
        <h3 className="font-semibold text-sm line-clamp-2 leading-tight text-foreground">
          {project.title}
        </h3>

        {/* Time Range */}
        <div className="flex items-center gap-2 text-xs">
          <Clock className="h-3.5 w-3.5 text-success" />
          <span className="text-success font-medium">
            {project.time_range.start} - {project.time_range.end}
          </span>
          <span className="text-muted-foreground">
            ({project.total_duration_formatted})
          </span>
        </div>

        {/* Total Duration */}
        <div className="text-xs text-muted-foreground">
          Total do video: {project.total_duration_formatted}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-medium text-muted-foreground">
              {project.channel || t('channel')}
            </span>
            <span className="text-xs text-muted-foreground/70">
              {formatDate(project.created_at)}
            </span>
          </div>

          {/* Clips Count Badge */}
          {project.clips_count > 0 && (
            <Badge variant="secondary" className="text-xs">
              {project.clips_count} clips
            </Badge>
          )}
        </div>

        {/* Download Transcript Button */}
        {onDownloadTranscript && project.status === 'analysis_complete' && (
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-2 text-xs"
            onClick={(e) => {
              e.stopPropagation();
              onDownloadTranscript();
            }}
          >
            <Download className="h-3.5 w-3.5 mr-2" />
            {t('downloadTranscript')}
          </Button>
        )}

        {/* Expired Notice */}
        {project.status === 'expired' && (
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground bg-muted rounded-lg py-2">
            <Download className="h-3.5 w-3.5" />
            <span>{t('expiredNotice')}</span>
          </div>
        )}
      </div>
    </Card>
  );
}
