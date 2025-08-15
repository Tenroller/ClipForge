import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { listJobs, type JobRecord } from '@/lib/api'

type JobSummary = {
  id: string
  status: string
  workflow?: 'moneyprinter' | 'brainrot'
  startedAt?: number
}

export default function ActivityPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [serverJobs, setServerJobs] = useState<JobRecord[]>([])

  useEffect(() => {
    try {
      const mp = JSON.parse(localStorage.getItem('creator:lastJob') || 'null')
      const br = JSON.parse(localStorage.getItem('compilations:lastJob') || 'null')
      const entries: JobSummary[] = []
      if (mp?.jobId) entries.push({ id: mp.jobId, status: mp.status || 'unknown', workflow: 'moneyprinter', startedAt: mp.startedAt })
      if (br?.jobId) entries.push({ id: br.jobId, status: br.status || 'unknown', workflow: 'brainrot', startedAt: br.startedAt })
      setJobs(entries)
    } catch {}
    ;(async () => {
      try {
        const js = await listJobs(50)
        setServerJobs(js)
      } catch {}
    })()
  }, [])

  return (
    <div className="container-page fade-in max-w-[1200px]">
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
              <div className="text-xs text-muted-foreground mb-2">Local recent jobs</div>
            {jobs.length === 0 ? (
              <div className="text-sm text-muted-foreground">No recent jobs</div>
            ) : jobs.map((j) => (
              <div key={`${j.workflow}-${j.id}`} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-[10px] uppercase">{j.workflow}</Badge>
                  <div className="text-sm font-medium">{j.id}</div>
                </div>
                <Badge variant={j.status === 'done' ? 'default' : j.status === 'error' ? 'destructive' : 'secondary'}>{j.status}</Badge>
              </div>
            ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}


