'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, Database, Loader2 } from "lucide-react";

interface SyncPanelProps {
  onSyncFromJobs: () => void;
  onSyncOrphaned: () => void;
  syncing: boolean;
}

export default function SyncPanel({ onSyncFromJobs, onSyncOrphaned, syncing }: SyncPanelProps) {
  return (
    <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="size-4" />
          Sync Videos
        </CardTitle>
        <CardDescription>
          Sync videos from job results or scan for orphaned files
        </CardDescription>
      </CardHeader>
      <CardContent>
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
                Syncing...
              </>
            ) : (
              <>
                <Database className="size-4 mr-2" />
                Sync from Jobs
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
                Syncing...
              </>
            ) : (
              <>
                <RefreshCw className="size-4 mr-2" />
                Sync Orphaned
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
