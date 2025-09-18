import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { getLatestManagedVideo, listManagedVideosByJob, ManagedVideoRecord, downloadUrl } from '@/lib/api'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

type DisplayEntry = {
  id: string
  jobId: string
  filename: string
  createdAt: string
  path: string
  download: string
  posted?: boolean
}

export default function DownloadsPage() {
  const [entries, setEntries] = useState<DisplayEntry[]>([])
  const [loading, setLoading] = useState(false)

  async function inferRecentJobIds(): Promise<string[]> {
    // Attempt to infer job IDs from localStorage legacy data
    const ids = new Set<string>()
    try {
      const mp = JSON.parse(localStorage.getItem('creator:lastResult') || 'null')
      const br = JSON.parse(localStorage.getItem('compilations:lastResult') || 'null')
      if (mp?.jobId) ids.add(mp.jobId)
      if (br?.jobId) ids.add(br.jobId)
      // Fallback: legacy entries with jobId nested
      if (mp?.job_id) ids.add(mp.job_id)
      if (br?.job_id) ids.add(br.job_id)
    } catch {}
    // Also gather any recent jobs persisted by jobManager
    try {
      const jm = JSON.parse(localStorage.getItem('jobManager:jobs') || '[]')
      if (Array.isArray(jm)) {
        jm.forEach((j: any) => { if (j?.id) ids.add(j.id) })
      }
    } catch {}
    return Array.from(ids)
  }

  async function refresh() {
    setLoading(true)
    try {
      const jobIds = await inferRecentJobIds()
      if (!jobIds.length) {
        setEntries([])
        return
      }
      const aggregated: DisplayEntry[] = []
      for (const jobId of jobIds) {
        const managed = await listManagedVideosByJob(jobId, 10)
        if (managed.length) {
          managed.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          for (const v of managed) {
            aggregated.push({
              id: v.id,
              jobId: v.job_id,
              filename: v.file_path.split('/').pop() || v.id,
              createdAt: v.created_at,
              path: v.file_path,
              download: `${API}${v.download_url || `/api/download?path=${encodeURIComponent(v.file_path)}`}`,
              posted: v.posted
            })
          }
        } else {
          // Fallback: attempt to use job's latest result if still in localStorage
          const latest = await getLatestManagedVideo(jobId)
          if (latest) {
            aggregated.push({
              id: latest.id,
              jobId: latest.job_id,
              filename: latest.file_path.split('/').pop() || latest.id,
              createdAt: latest.created_at,
              path: latest.file_path,
              download: `${API}${latest.download_url || `/api/download?path=${encodeURIComponent(latest.file_path)}`}`,
              posted: latest.posted
            })
          }
        }
      }
      // Sort across all videos newest first
      aggregated.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      setEntries(aggregated)
    } catch (e) {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <Card className="enhanced-card">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Downloads (Managed Videos)</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</Button>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            {entries.length === 0 ? (
              <div className="text-sm text-muted-foreground">No managed videos found for recent jobs</div>
            ) : entries.map(e => (
              <div key={e.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                <div className="text-sm font-medium truncate max-w-[60ch]" title={e.filename}>{e.filename}</div>
                <a className="muted-link font-medium" href={e.download} download target="_blank" rel="noreferrer">Download</a>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}



