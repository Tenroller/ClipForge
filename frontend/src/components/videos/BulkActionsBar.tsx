'use client';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Download, Check, X, Trash2 } from "lucide-react";
import { useTranslations } from 'next-intl';

interface BulkActionsBarProps {
  selectedCount: number;
  onDownloadAll: () => void;
  onMarkAllPosted: () => void;
  onDeleteAll?: () => void;
  onClearSelection: () => void;
  totalUnposted?: number;
}

export default function BulkActionsBar({
  selectedCount,
  onDownloadAll,
  onMarkAllPosted,
  onDeleteAll,
  onClearSelection,
  totalUnposted = 0
}: BulkActionsBarProps) {
  const t = useTranslations('videos');
  
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-5 duration-300">
      <Card className="shadow-2xl border-2">
        <div className="flex items-center gap-4 px-6 py-4">
          {/* Selection Count */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm">
              {selectedCount}
            </div>
            <span className="font-medium text-sm">
              {selectedCount} {selectedCount !== 1 ? t('videos') : t('video')} {t('selected')}
            </span>
          </div>

          {/* Divider */}
          <div className="h-8 w-px bg-border" />

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onDownloadAll}
              className="h-9"
            >
              <Download className="size-4 mr-2" />
              {t('bulkActions.downloadAll')}
            </Button>

            {totalUnposted > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={onMarkAllPosted}
                className="h-9"
              >
                <Check className="size-4 mr-2" />
                {t('bulkActions.markAllPosted')} ({totalUnposted})
              </Button>
            )}

            {onDeleteAll && (
              <Button
                variant="outline"
                size="sm"
                onClick={onDeleteAll}
                className="h-9 text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="size-4 mr-2" />
                {t('bulkActions.deleteAll')}
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="h-9"
            >
              <X className="size-4 mr-2" />
              {t('bulkActions.clearSelection')}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
