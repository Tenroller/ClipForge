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
    <div className="fixed bottom-4 sm:bottom-8 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-5 duration-300 w-[calc(100%-2rem)] sm:w-auto max-w-2xl safe-area-bottom">
      <Card className="border rounded-xl bg-card shadow-lg">
        <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-5 px-4 sm:px-7 py-3 sm:py-5">
          {/* Selection Count */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-base">
              {selectedCount}
            </div>
            <span className="font-semibold text-sm sm:text-base">
              {selectedCount} {selectedCount !== 1 ? t('videos') : t('video')} {t('selected')}
            </span>
          </div>

          {/* Divider - hidden on mobile */}
          <div className="hidden sm:block h-10 w-px bg-border" />

          {/* Actions */}
          <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={onDownloadAll}
              className="h-11 font-semibold"
            >
              <Download className="size-4 mr-2" />
              <span className="hidden sm:inline">{t('bulkActions.downloadAll')}</span>
              <span className="sm:hidden">{t('download')}</span>
            </Button>

            {totalUnposted > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={onMarkAllPosted}
                className="h-11 font-semibold"
              >
                <Check className="size-4 mr-2" />
                <span className="hidden sm:inline">{t('bulkActions.markAllPosted')} ({totalUnposted})</span>
                <span className="sm:hidden">{t('markPosted')}</span>
              </Button>
            )}

            {onDeleteAll && (
              <Button
                variant="outline"
                size="sm"
                onClick={onDeleteAll}
                className="h-11 font-semibold text-destructive hover:text-destructive hover:bg-destructive/10 hover:border-destructive/50"
              >
                <Trash2 className="size-4 mr-2" />
                <span className="hidden sm:inline">{t('bulkActions.deleteAll')}</span>
                <span className="sm:hidden">{t('delete')}</span>
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="h-11 font-semibold"
            >
              <X className="size-4 mr-2" />
              <span className="hidden sm:inline">{t('bulkActions.clearSelection')}</span>
              <span className="sm:hidden">{t('clear')}</span>
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
