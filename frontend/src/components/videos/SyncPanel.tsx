'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, Database, Loader2 } from "lucide-react";
import { useTranslations } from 'next-intl';

interface SyncPanelProps {
  onSyncFromJobs: () => void;
  onSyncOrphaned: () => void;
  syncing: boolean;
}

export default function SyncPanel({ onSyncFromJobs, onSyncOrphaned, syncing }: SyncPanelProps) {
  const t = useTranslations('videos.sync');
  return (
    <Card className="border rounded-xl border-blue-200 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-800/30 shadow-md backdrop-blur-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="size-4" />
          {t('title')}
        </CardTitle>
        <CardDescription>
          {t('description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Button
            variant="outline"
            onClick={onSyncFromJobs}
            disabled={syncing}
            className="w-full"
          >
            {syncing ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                {t('syncing')}
              </>
            ) : (
              <>
                <Database className="size-4 mr-2" />
                {t('fromJobs')}
              </>
            )}
          </Button>
          <Button
            variant="outline"
            onClick={onSyncOrphaned}
            disabled={syncing}
            className="w-full"
          >
            {syncing ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                {t('syncing')}
              </>
            ) : (
              <>
                <RefreshCw className="size-4 mr-2" />
                {t('orphaned')}
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
