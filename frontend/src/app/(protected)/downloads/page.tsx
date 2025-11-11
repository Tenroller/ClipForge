'use client';

import { useJobs } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Download, Loader2, Video as VideoIcon, RefreshCw } from "lucide-react";

export default function DownloadsPage() {
  const { data: jobs = [], isLoading, refetch } = useJobs({ limit: 100 });

  // Filter for completed jobs with output URLs
  const completedJobs = jobs.filter(
    (job) => (job.status === 'completed' || job.status === 'done') && job.output_url
  );

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'N/A';
    }
  };

  const getWorkflowLabel = (workflow: string) => {
    switch (workflow) {
      case 'moneyprinter':
        return 'AI Video';
      case 'brainrot':
        return 'Compilation';
      default:
        return workflow;
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    const kb = bytes / 1024;
    const mb = kb / 1024;
    const gb = mb / 1024;

    if (gb >= 1) return `${gb.toFixed(2)} GB`;
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${kb.toFixed(2)} KB`;
  };

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Downloads</h1>
        <p className="text-muted-foreground mt-2">Download your completed videos</p>
      </div>

      <Card className="enhanced-card">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
              <VideoIcon className="size-4 text-white" />
            </div>
            <div>
              <div>Completed Videos</div>
              <p className="text-sm font-normal text-muted-foreground">
                {completedJobs.length} videos available
              </p>
            </div>
          </CardTitle>
          <Button size="sm" variant="outline" onClick={() => refetch()} disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                Refreshing...
              </>
            ) : (
              <>
                <RefreshCw className="size-4 mr-2" />
                Refresh
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading && completedJobs.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="size-5 mr-2 animate-spin" />
              Loading videos...
            </div>
          ) : completedJobs.length === 0 ? (
            <div className="text-center py-12">
              <VideoIcon className="size-12 text-muted-foreground/50 mx-auto mb-4" />
              <p className="text-muted-foreground">No completed videos found</p>
              <p className="text-sm text-muted-foreground mt-2">
                Generate your first video to see it here
              </p>
            </div>
          ) : (
            <div className="grid gap-3">
              {completedJobs.map((job) => {
                const filename = job.output_url
                  ? job.output_url.split('/').pop() || `video_${job.id.substring(0, 8)}.mp4`
                  : `video_${job.id.substring(0, 8)}.mp4`;

                return (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-3">
                        <VideoIcon className="size-4 text-muted-foreground shrink-0" />
                        <span
                          className="text-sm font-medium truncate max-w-[50ch]"
                          title={filename}
                        >
                          {filename}
                        </span>
                        <Badge variant="outline" className="text-[10px] uppercase shrink-0">
                          {getWorkflowLabel(job.workflow)}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>Job ID: {job.id.substring(0, 16)}...</span>
                        {job.created_at && <span>Created: {formatDate(job.created_at)}</span>}
                        {job.duration_seconds && (
                          <span>
                            Duration: {Math.floor(job.duration_seconds / 60)}m{' '}
                            {job.duration_seconds % 60}s
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4 shrink-0">
                      <Button variant="outline" size="sm" asChild>
                        <a
                          href={job.output_url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2"
                        >
                          <VideoIcon className="size-3" />
                          View
                        </a>
                      </Button>
                      <Button size="sm" asChild>
                        <a
                          href={job.output_url}
                          download
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2"
                        >
                          <Download className="size-3" />
                          Download
                        </a>
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stats Card */}
      {completedJobs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{completedJobs.length}</div>
              <p className="text-xs text-muted-foreground">Total Videos</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {completedJobs.filter((j) => j.workflow === 'moneyprinter').length}
              </div>
              <p className="text-xs text-muted-foreground">AI Generated</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {completedJobs.filter((j) => j.workflow === 'brainrot').length}
              </div>
              <p className="text-xs text-muted-foreground">Compilations</p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
