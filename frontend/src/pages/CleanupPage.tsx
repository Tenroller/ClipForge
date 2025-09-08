import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { Badge } from '@/components/components/ui/badge'

import { FaTrash, FaSpinner, FaCheck, FaExclamationTriangle, FaFile, FaFolder, FaRedo } from 'react-icons/fa'
import { getTempFilesStats, cleanupTempFiles, type TempFileStats, type CleanupResult } from '@/lib/api'
import { toast } from 'sonner'

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}

export default function CleanupPage() {
  const [stats, setStats] = useState<TempFileStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [cleaning, setCleaning] = useState(false)
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadStats = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getTempFilesStats()
      setStats(data)
      toast.success('Statistics refreshed')
      devLog('Loaded temp file stats:', data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load temp file statistics'
      setError(errorMessage)
      toast.error('Failed to refresh statistics', { description: errorMessage })
      devLog('Failed to load temp file stats:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCleanup = async () => {
    if (!stats || stats.total_files === 0) return

    try {
      setCleaning(true)
      setError(null)
      setCleanupResult(null)

      toast.loading('Cleaning up temporary files...', { id: 'cleanup' })

      const result = await cleanupTempFiles()
      setCleanupResult(result)

      // Reload stats to show the cleanup results
      await loadStats()

      // Show success toast
      toast.success(`Cleanup completed! Deleted ${result.deleted_files} files, freed ${result.freed_space_mb.toFixed(2)} MB`, {
        id: 'cleanup',
        description: `Cleaned ${result.directories_cleaned.length} directories`
      })

      devLog('Cleanup completed:', result)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to cleanup temp files'
      setError(errorMessage)
      toast.error('Cleanup failed', { id: 'cleanup', description: errorMessage })
      devLog('Cleanup failed:', err)
    } finally {
      setCleaning(false)
    }
  }

  useEffect(() => {
    loadStats()
  }, [])

  const formatFileSize = (sizeMb: number): string => {
    if (sizeMb < 1) {
      return `${(sizeMb * 1024).toFixed(0)} KB`
    } else if (sizeMb < 1024) {
      return `${sizeMb.toFixed(1)} MB`
    } else {
      return `${(sizeMb / 1024).toFixed(1)} GB`
    }
  }

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString)
      return date.toLocaleString()
    } catch {
      return dateString
    }
  }

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">System Cleanup</h1>
            <p className="text-muted-foreground">Manage temporary files and free up disk space</p>
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
          <Card className="border-green-200 bg-green-50/50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  <FaCheck className="size-5 text-green-600" />
                </div>
                <div>
                  <div className="font-semibold text-green-800">Cleanup completed successfully!</div>
                  <div className="text-sm text-green-700 mt-1">
                    Deleted {cleanupResult.deleted_files} files, freed {cleanupResult.freed_space_mb.toFixed(2)} MB of space
                    {cleanupResult.errors.length > 0 && (
                      <div className="mt-2 text-yellow-700">
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

                  {/* Recent Files */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Recent Files:</h4>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {dir.files.map((file) => (
                        <div key={file.name} className="flex items-center justify-between py-1 px-2 rounded bg-muted/20">
                          <div className="flex items-center gap-2">
                            <FaFile className="size-3 text-muted-foreground" />
                            <span className="text-sm font-mono truncate max-w-xs">{file.name}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{formatFileSize(file.size_mb)}</span>
                            <span>{formatDate(file.modified)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Cleanup Errors */}
        {cleanupResult && cleanupResult.errors.length > 0 && (
          <Card className="border-yellow-200 bg-yellow-50/50">
            <CardHeader>
              <CardTitle className="text-yellow-800 flex items-center gap-2">
                <FaExclamationTriangle className="size-4" />
                Cleanup Warnings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {cleanupResult.errors.map((error, index) => (
                  <div key={index} className="text-sm text-yellow-700 bg-yellow-100 p-2 rounded">
                    {error}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
