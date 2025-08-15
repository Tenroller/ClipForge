import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'

type FileEntry = { path: string; mtime: number }

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function DownloadsPage() {
  const [files, setFiles] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      // Try to read from last known output dir from either page
      const mp = JSON.parse(localStorage.getItem('creator:lastResult') || 'null')
      const br = JSON.parse(localStorage.getItem('compilations:lastResult') || 'null')
      const outputDir = br?.output_dir || mp?.output_dir
      if (!outputDir) { setFiles([]); return }
      const listRes = await fetch(`${API}/api/list-videos?dir=${encodeURIComponent(outputDir)}`)
      const listJson = await listRes.json()
      const result: FileEntry[] = Array.isArray(listJson?.files) ? listJson.files : []
      result.sort((a, b) => b.mtime - a.mtime)
      setFiles(result)
    } catch {
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  return (
    <div className="container-page fade-in max-w-[1200px]">
      <Card className="enhanced-card">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Downloads</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</Button>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            {files.length === 0 ? (
              <div className="text-sm text-muted-foreground">No files found</div>
            ) : files.map((f) => {
              const url = `${API}/api/download?path=${encodeURIComponent(f.path)}`
              return (
                <div key={f.path} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                  <div className="text-sm font-medium truncate max-w-[60ch]">{f.path}</div>
                  <a className="muted-link font-medium" href={url} download target="_blank" rel="noreferrer">Download</a>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}



