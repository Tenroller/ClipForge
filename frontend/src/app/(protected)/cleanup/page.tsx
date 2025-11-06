'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { FaTrash, FaSpinner, FaCheck, FaExclamationTriangle, FaFile, FaFolder, FaRedo } from 'react-icons/fa';
import { getTempFilesStats, cleanupTempFiles, type TempFileStats, type CleanupResult } from '@/lib/api';

export default function CleanupPage() {
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
        title: 'Statistics Refreshed',
        description: 'Temporary file statistics have been updated',
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load temp file statistics';
      toast({
        title: 'Failed to Refresh Statistics',
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
        title: 'Cleanup Completed',
        description: `Deleted ${result.deleted_files} files, freed ${result.freed_space_mb.toFixed(2)} MB`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to cleanup temp files';
      toast({
        title: 'Cleanup Failed',
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
    <div className="container-page fade-in max-w-[1200px]">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">System Cleanup</h1>
            <p className="text-muted-foreground mt-2">Manage temporary files and free up disk space</p>
          </div>
          <Button
            onClick={loadStats}
            disabled={loading}
            variant="outline"
            className="flex items-center gap-2"
          >
            {loading ? <FaSpinner className="size-4 animate-spin" /> : <FaRedo className="size-4" />}
            Refresh Stats
          </Button>
        </div>

        {/* Cleanup Status Card */}
        {cleanupResult && (
          <Card className="border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-800/30">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  <FaCheck className="size-5 text-green-600" />
                </div>
                <div>
                  <div className="font-semibold text-green-800 dark:text-green-200">Cleanup completed successfully!</div>
                  <div className="text-sm text-green-700 dark:text-green-300 mt-1">
                    Deleted {cleanupResult.deleted_files} files, freed {cleanupResult.freed_space_mb.toFixed(2)} MB of space
                    {cleanupResult.errors.length > 0 && (
                      <div className="mt-2 text-yellow-700 dark:text-yellow-400">
                        {cleanupResult.errors.length} error(s) occurred during cleanup
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats Overview */}
        <Card className="enhanced-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FaFolder className="size-5" />
              Temporary Files Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <FaSpinner className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading statistics...</span>
              </div>
            ) : stats ? (
              <div className="space-y-4">
                {/* Summary Stats */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-4 rounded-lg bg-muted/30 border">
                    <div className="text-2xl font-bold text-primary">{stats.total_files}</div>
                    <div className="text-sm text-muted-foreground">Total Files</div>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-muted/30 border">
                    <div className="text-2xl font-bold text-primary">{formatFileSize(stats.total_size_mb)}</div>
                    <div className="text-sm text-muted-foreground">Total Size</div>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-muted/30 border">
                    <div className="text-2xl font-bold text-primary">{stats.directories.length}</div>
                    <div className="text-sm text-muted-foreground">Directories</div>
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
                        <FaSpinner className="size-5 animate-spin" />
                        Cleaning up files...
                      </>
                    ) : (
                      <>
                        <FaTrash className="size-5" />
                        Clean Up All Temp Files
                      </>
                    )}
                  </Button>
                </div>

                {stats.total_files === 0 && (
                  <div className="text-center py-4 text-muted-foreground">
                    <FaCheck className="size-8 mx-auto mb-2 text-green-500" />
                    No temporary files found. Your system is clean!
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Failed to load temporary file statistics
              </div>
            )}
          </CardContent>
        </Card>

        {/* Directory Details */}
        {stats && stats.directories.length > 0 && (
          <div className="grid gap-4">
            <h2 className="text-xl font-semibold">Directory Details</h2>
            {stats.directories.map((dir) => (
              <Card key={dir.path} className="enhanced-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FaFolder className="size-4" />
                    {dir.path.split(/[/\\]/).pop() || dir.path}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <Badge variant="outline">{dir.file_count} files</Badge>
                      <span className="text-sm text-muted-foreground">
                        {formatFileSize(dir.total_size_mb)}
                      </span>
                    </div>
                  </div>

                  {/* Directory Information */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Directory Information:</h4>
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <span><strong>Path:</strong> {dir.path}</span>
                        </div>
                        {dir.oldest_file_age_hours != null && (
                          <div className="flex items-center gap-2 mt-1">
                            <span><strong>Oldest file:</strong> {dir.oldest_file_age_hours.toFixed(1)} hours old</span>
                          </div>
                        )}
                      </div>
                      {dir.files && dir.files.length > 0 ? (
                        <div className="space-y-1 max-h-40 overflow-y-auto">
                          {dir.files.map((file) => (
                            <div key={file.name} className="flex items-center justify-between py-1 px-2 rounded bg-muted/20">
                              <div className="flex items-center gap-2 flex-1 min-w-0">
                                <FaFile className="size-3 text-muted-foreground shrink-0" />
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
                          <FaFolder className="inline size-3 mr-2" />
                          Directory details not available
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
          <Card className="border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20 dark:border-yellow-800/30">
            <CardHeader>
              <CardTitle className="text-yellow-800 dark:text-yellow-200 flex items-center gap-2">
                <FaExclamationTriangle className="size-4" />
                Cleanup Warnings
              </CardTitle>
            </CardHeader>
            <CardContent>
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
