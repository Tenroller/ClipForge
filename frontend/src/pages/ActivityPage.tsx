import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { Button } from '@/components/components/ui/button'
import { Eye } from 'lucide-react'
import { listJobs, type JobRecord } from '@/lib/api'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'
import ResultPanel from '@/components/ResultPanel'
import ResumableJobsPanel from '@/components/ResumableJobsPanel'

export default function ActivityPage() {
  const [serverJobs, setServerJobs] = useState<JobRecord[]>([])
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const jobManager = useJobManager()

  useEffect(() => {
    // Fetch server jobs from API
    (async () => {
      try {
        const js = await listJobs(50)
        setServerJobs(js)
      } catch {}
    })()
  }, [])

  const handleViewResult = (job: ManagedJob) => {
    setSelectedResult(job)
  }

  const handleCloseResult = () => {
    setSelectedResult(null)
  }

  // If showing results, render the result panel
  if (selectedResult) {
    return (
      <div className="container-page fade-in max-w-[1200px]">
        <ResultPanel
          job={selectedResult}
          onClose={handleCloseResult}
        />
      </div>
    )
  }

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <div className="space-y-6">
        {/* Resumable Jobs Panel */}
        <ResumableJobsPanel jobManager={jobManager} />
        
        {/* Regular Activity Card */}
        <Card className="enhanced-card">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-5">
              <div>
                <div className="text-xs text-muted-foreground mb-2">Server jobs</div>
                {serverJobs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No server jobs</div>
                ) : serverJobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-[10px] uppercase">{j.workflow}</Badge>
                      <div className="text-sm font-medium">{j.id}</div>
                    </div>
                    <Badge variant={j.status === 'done' ? 'default' : j.status === 'error' ? 'destructive' : 'secondary'}>{j.status}</Badge>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-2">Managed jobs ({jobManager.jobs.length})</div>
                {jobManager.jobs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No managed jobs</div>
                ) : jobManager.jobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-[10px] uppercase">{j.workflow}</Badge>
                      <div className="text-sm font-medium">{j.id}</div>
                      <div className="text-xs text-muted-foreground">
                        {j.progress}% - {j.step || 'Initializing...'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={j.status === 'done' ? 'default' : j.status === 'error' ? 'destructive' : 'secondary'}>{j.status}</Badge>
                      {j.status === 'done' && j.previewUrl && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleViewResult(j)}
                          className="h-7 px-2 text-xs"
                        >
                          <Eye className="size-3 mr-1" />
                          View
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}


