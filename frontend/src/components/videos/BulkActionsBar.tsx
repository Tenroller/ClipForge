'use client';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { FaDownload, FaCheck, FaTimes, FaTrash } from 'react-icons/fa';

interface BulkActionsBarProps {
  selectedCount: number;
  onDownloadAll: () => void;
  onMarkAllPosted: () => void;
  onClearSelection: () => void;
  totalUnposted?: number;
}

export default function BulkActionsBar({
  selectedCount,
  onDownloadAll,
  onMarkAllPosted,
  onClearSelection,
  totalUnposted = 0
}: BulkActionsBarProps) {
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
              {selectedCount} video{selectedCount !== 1 ? 's' : ''} selected
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
              <FaDownload className="size-4 mr-2" />
              Download All
            </Button>

            {totalUnposted > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={onMarkAllPosted}
                className="h-9"
              >
                <FaCheck className="size-4 mr-2" />
                Mark {totalUnposted} as Posted
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="h-9"
            >
              <FaTimes className="size-4 mr-2" />
              Clear
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
