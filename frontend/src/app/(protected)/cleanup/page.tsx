'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { Trash2, Loader2, Check, AlertTriangle, File, Folder, RefreshCw } from "lucide-react";
import { getTempFilesStats, cleanupTempFiles, type TempFileStats, type CleanupResult } from '@/lib/api';

export default function CleanupPage() {
  const t = useTranslations('cleanup');
  const { toast } = useToast();
  const [stats, setStats] = useState<TempFileStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null);

  const loadStats = async () => {
    try {
      setLoading(true);
      const data = await getTempFilesStats();
      setStats(data);
      toast({
        title: t('statisticsRefreshed'),
        description: t('statsUpdated'),
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('failedToLoad');
      toast({
        title: t('failedToRefresh'),
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    if (!stats || stats.total_files === 0) return;

    try {
      setCleaning(true);
      setCleanupResult(null);

      const result = await cleanupTempFiles();
      setCleanupResult(result);

      // Reload stats to show the cleanup results
      await loadStats();

      // Show success toast
      toast({
        title: t('cleanupCompleted'),
        description: t('deletedFiles', { count: result.deleted_files, size: result.freed_space_mb.toFixed(2) }),
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('failedToCleanup');
      toast({
        title: t('cleanupFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setCleaning(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const formatFileSize = (sizeMb: number): string => {
    if (sizeMb < 1) {
      return `${(sizeMb * 1024).toFixed(0)} KB`;
    } else if (sizeMb < 1024) {
      return `${sizeMb.toFixed(1)} MB`;
    } else {
      return `${(sizeMb / 1024).toFixed(1)} GB`;
    }
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
      <div className="space-y-6">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <div className="inline-block">
              <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                {t('title')}
              </h1>
              <div className="h-1 w-24 bg-gradient-to-r from-primary to-accent rounded-full mt-2" />
            </div>
            <p className="text-base text-muted-foreground max-w-2xl">
              {t('description')}
            </p>
          </div>
          <Button
            onClick={loadStats}
            disabled={loading}
            variant="outline"
          >
            {loading ? <Loader2 className="size-4 mr-2 animate-spin" /> : <RefreshCw className="size-4 mr-2" />}
            {t('refreshStats')}
          </Button>
        </div>

        {/* Cleanup Status Card */}
        {cleanupResult && (
          <Card className="border rounded-xl border-green-200 bg-green-50/50 dark:bg-green-950/20 dark:border-green-800/30 shadow-md backdrop-blur-sm">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  <Check className="size-5 text-green-600" />
                </div>
                <div>
                  <div className="font-semibold text-green-800 dark:text-green-200">{t('cleanupSuccess')}</div>
                  <div className="text-sm text-green-700 dark:text-green-300 mt-1">
                    {t('deletedFiles', { count: cleanupResult.deleted_files, size: cleanupResult.freed_space_mb.toFixed(2) })}
                    {cleanupResult.errors.length > 0 && (
                      <div className="mt-2 text-yellow-700 dark:text-yellow-400">
                        {t('errorsOccurred', { count: cleanupResult.errors.length })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats Overview */}
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Folder className="size-5" />
              {t('overview.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">{t('loading')}</span>
              </div>
            ) : stats ? (
              <div className="space-y-5">
                {/* Summary Stats */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                  <div className="text-center p-5 rounded-xl bg-muted/30 border border-muted shadow-sm">
                    <div className="text-2xl font-bold text-primary">{stats.total_files}</div>
                    <div className="text-sm text-muted-foreground mt-1">{t('overview.totalFiles')}</div>
                  </div>
                  <div className="text-center p-5 rounded-xl bg-muted/30 border border-muted shadow-sm">
                    <div className="text-2xl font-bold text-primary">{formatFileSize(stats.total_size_mb)}</div>
                    <div className="text-sm text-muted-foreground mt-1">{t('overview.totalSize')}</div>
                  </div>
                  <div className="text-center p-5 rounded-xl bg-muted/30 border border-muted shadow-sm">
                    <div className="text-2xl font-bold text-primary">{stats.directories.length}</div>
                    <div className="text-sm text-muted-foreground mt-1">{t('overview.directories')}</div>
                  </div>
                </div>

                {/* Cleanup Button */}
                <div className="flex justify-center pt-4">
                  <Button
                    onClick={handleCleanup}
                    disabled={cleaning || stats.total_files === 0}
                    size="lg"
                    className="flex items-center gap-2 px-8"
                    variant={stats.total_files === 0 ? 'outline' : 'destructive'}
                  >
                    {cleaning ? (
                      <>
                        <Loader2 className="size-5 animate-spin" />
                        {t('actions.cleaning')}
                      </>
                    ) : (
                      <>
                        <Trash2 className="size-5" />
                        {t('actions.cleanAll')}
                      </>
                    )}
                  </Button>
                </div>

                {stats.total_files === 0 && (
                  <div className="text-center py-4 text-muted-foreground">
                    <Check className="size-8 mx-auto mb-2 text-green-500" />
                    {t('overview.noFiles')}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                {t('overview.failed')}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Directory Details */}
        {stats && stats.directories.length > 0 && (
          <div className="grid gap-5">
            <h2 className="text-xl font-semibold">{t('directoryDetails.title')}</h2>
            {stats.directories.map((dir) => (
              <Card key={dir.path} className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
                <CardHeader className="pb-4">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Folder className="size-4" />
                    {dir.path.split(/[/\\]/).pop() || dir.path}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <Badge variant="outline">{dir.file_count} {t('directoryDetails.files')}</Badge>
                      <span className="text-sm text-muted-foreground">
                        {formatFileSize(dir.total_size_mb)}
                      </span>
                    </div>
                  </div>

                  {/* Directory Information */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">{t('directoryDetails.directoryInfo')}</h4>
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <span><strong>{t('directoryDetails.path')}</strong> {dir.path}</span>
                        </div>
                        {dir.oldest_file_age_hours != null && (
                          <div className="flex items-center gap-2 mt-1">
                            <span><strong>{t('directoryDetails.oldestFile')}</strong> {t('directoryDetails.hoursOld', { hours: dir.oldest_file_age_hours.toFixed(1) })}</span>
                          </div>
                        )}
                      </div>
                      {dir.files && dir.files.length > 0 ? (
                        <div className="space-y-1 max-h-40 overflow-y-auto">
                          {dir.files.map((file) => (
                            <div key={file.name} className="flex items-center justify-between py-1 px-2 rounded bg-muted/20">
                              <div className="flex items-center gap-2 flex-1 min-w-0">
                                <File className="size-3 text-muted-foreground shrink-0" />
                                <span className="text-sm font-mono truncate">{file.name}</span>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0 ml-2">
                                <span>{formatFileSize(file.size_mb)}</span>
                                <span>{formatDate(file.modified)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-sm text-muted-foreground py-2">
                          <Folder className="inline size-3 mr-2" />
                          {t('directoryDetails.notAvailable')}
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Cleanup Errors */}
        {cleanupResult && cleanupResult.errors.length > 0 && (
          <Card className="border rounded-xl border-yellow-200 bg-yellow-50/50 dark:bg-yellow-950/20 dark:border-yellow-800/30 shadow-md backdrop-blur-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-yellow-800 dark:text-yellow-200 flex items-center gap-2">
                <AlertTriangle className="size-4" />
                {t('warnings.title')}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-2">
                {cleanupResult.errors.map((error, index) => (
                  <div key={index} className="text-sm text-yellow-700 dark:text-yellow-300 bg-yellow-100 dark:bg-yellow-900/30 p-2 rounded">
                    {error}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
