import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/components/ui/card'
import { Input } from '@/components/components/ui/input'
import { Label } from '@/components/components/ui/label'
import { Button } from '@/components/components/ui/button'
import { Loader2, BadgeCheck, Brain, HelpCircle, RefreshCw } from 'lucide-react'
import JobPanel from '@/components/components/job-panel'

type Job = {
  status: string
  step?: string
  result?: any
  error?: string
}

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function CompilationsPage() {
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<any>(null)
  const [lastRun, setLastRun] = useState<{ workflow: 'brainrot'; payload: any } | null>(null)

  // Persistence helpers
  function saveLastJob(partial: Partial<{ jobId: string; status: string; startedAt: number; payload: any }>) {
    try {
      const prev = JSON.parse(localStorage.getItem('compilations:lastJob') || '{}')
      const next = { ...prev, ...partial, workflow: 'brainrot' }
      localStorage.setItem('compilations:lastJob', JSON.stringify(next))
    } catch {}
  }
  function saveLastResult(result: any) {
    try {
      localStorage.setItem('compilations:lastResult', JSON.stringify(result || {}))
    } catch {}
  }

  useEffect(() => {
    // try restore on mount
    try {
      const lastJob = JSON.parse(localStorage.getItem('compilations:lastJob') || 'null') as any
      const lastResult = JSON.parse(localStorage.getItem('compilations:lastResult') || 'null') as any
      if (lastResult?.output) {
        const dl = `${API}/api/download?path=${encodeURIComponent(lastResult.output)}`
        setPreviewUrl(dl)
      } else if (lastResult?.output_dir) {
        // will be handled post-finish
      }
      if (lastJob?.jobId) {
        setJobId(lastJob.jobId)
        const s = String(lastJob.status || '').toLowerCase()
        const isTerminal = ['done', 'error', 'cancelled'].includes(s)
        if (!isTerminal) {
          connectJobUpdates(lastJob.jobId)
        }
      }
    } catch {}
  }, [])

  async function startBrainrot(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const payload = {
      youtubeUrl: String(form.get('youtubeUrl') || ''),
      numCompilations: Number(form.get('numCompilations') || 1),
      minDuration: Number(form.get('minDuration') || 60),
      maxDuration: Number(form.get('maxDuration') || 110),
      maxReuse: Number(form.get('maxReuse') || 3),
    }
    if (!payload.youtubeUrl) return toast.error('YouTube URL is required')
    setBusy(true)
    try {
      const res = await fetch(`${API}/api/brainrot/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setJobId(data.jobId)
      toast.success('Job started')
      connectJobUpdates(data.jobId)
      setLastRun({ workflow: 'brainrot', payload })
      saveLastJob({ jobId: data.jobId, status: 'started', startedAt: Date.now(), payload })
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function handlePreviewForJob(data: Job) {
    try {
      if (!data?.result) return
      if (typeof (data as any).result.output === 'string') {
        const path = (data as any).result.output
        const dl = `${API}/api/download?path=${encodeURIComponent(path)}`
        setPreviewUrl(dl)
      } else if (typeof (data as any).result.output_dir === 'string') {
        const dir = (data as any).result.output_dir
        const listRes = await fetch(`${API}/api/list-videos?dir=${encodeURIComponent(dir)}`)
        const listJson = await listRes.json()
        const files: Array<{ path: string; mtime: number }> = Array.isArray(listJson?.files) ? listJson.files : []
        files.sort((a, b) => b.mtime - a.mtime)
        if (files[0]?.path) {
          const dl = `${API}/api/download?path=${encodeURIComponent(files[0].path)}`
          setPreviewUrl(dl)
        }
      }
    } catch {
      // ignore
    }
  }

  function connectJobUpdates(id: string) {
    try { if (wsRef.current) { wsRef.current.close() } } catch {}
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    setJob(null)
    setPreviewUrl(null)

    const wsUrl = `${API.replace('http', 'ws')}/ws/jobs/${id}`
    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data) as Job
          setJob(data)
          if (data.status === 'done') {
            await handlePreviewForJob(data)
          }
          saveLastJob({ jobId: id, status: data.status })
          if ((data as any)?.result) {
            saveLastResult((data as any).result)
          }
        } catch {}
        try { ws.send('ack') } catch {}
      }
      ws.onopen = () => {
        try { ws.send('hello') } catch {}
      }
      ws.onerror = () => {
        startPollingFallback(id)
      }
      ws.onclose = () => {
        if (!job || (job.status !== 'done' && job.status !== 'error' && job.status !== 'cancelled')) {
          startPollingFallback(id)
        }
      }
    } catch {
      startPollingFallback(id)
    }
  }

  function startPollingFallback(id: string) {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/jobs/${id}`)
        const data = (await res.json()) as Job
        setJob(data)
        if (data.status === 'done') {
          await handlePreviewForJob(data)
        }
        saveLastJob({ jobId: id, status: data.status })
        if ((data as any)?.result) {
          saveLastResult((data as any).result)
        }
        if (data.status === 'done' || data.status === 'error' || data.status === 'cancelled') {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      } catch {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 1500)
  }

  useEffect(() => {
    return () => {
      try { if (wsRef.current) wsRef.current.close() } catch {}
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [])

  const stepOrderBrainrot = [
    'process_video',
    'generate_compilations',
    'done',
  ] as const

  const progress = useMemo(() => {
    const current = (job?.step || (job?.status === 'done' ? 'done' : 'init')) as string
    const hasResult = !!previewUrl || !!(job as any)?.result?.output || !!(job as any)?.result?.output_dir
    const idxBase = stepOrderBrainrot.indexOf(current as any)
    const idx = hasResult || job?.status === 'done' ? stepOrderBrainrot.length - 1 : Math.max(0, idxBase - 1)
    return stepOrderBrainrot.map(s => ({ 
      key: s, 
      label: labelForStep(s), 
      done: idx >= stepOrderBrainrot.indexOf(s),
      active: !hasResult && job?.status !== 'done' && s === current
    }))
  }, [job?.step, job?.status, previewUrl])

  function labelForStep(step: string) {
    switch (step) {
      case 'process_video': return 'Process Video'
      case 'generate_compilations': return 'Generate Compilations'
      case 'done': return 'Done'
      default: return step
    }
  }

  return (
    <div className="container-page fade-in max-w-[1760px]">
      <div className="slide-in">
        <div className="grid grid-cols-12 gap-4 lg:gap-5 xl:gap-6 items-start">
          <div className="col-span-12 lg:col-span-3 xl:col-span-3 2xl:col-span-3">
            <Card className="enhanced-card">
              <CardHeader className="py-3">
                <CardTitle className="text-base flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                    <Brain className="size-4 text-white" />
                  </div>
                  Compilation Generator
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={startBrainrot} id="brainrot-form" aria-describedby="br-help">
                  <div className="form-section compact-section">
                    <div className="form-section-title">
                      <Brain className="size-4 text-indigo-500" />
                      Source Video
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="youtubeUrl">YouTube URL</Label>
                      <Input id="youtubeUrl" name="youtubeUrl" placeholder="https://youtu.be/..." required aria-required="true" />
                      <p id="br-help" className="text-xs text-muted-foreground">Paste a single video URL. Required.</p>
                    </div>
                  </div>
                  
                  <div className="form-section compact-section">
                    <div className="form-section-title">
                      <HelpCircle className="size-4 text-purple-500" />
                      Configuration
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="numCompilations">Compilations</Label>
                        <Input id="numCompilations" name="numCompilations" type="number" defaultValue={1} min={1} />
                      </div>
                      <div>
                        <Label htmlFor="minDuration">Min Duration</Label>
                        <Input id="minDuration" name="minDuration" type="number" defaultValue={60} />
                      </div>
                      <div>
                        <Label htmlFor="maxDuration">Max Duration</Label>
                        <Input id="maxDuration" name="maxDuration" type="number" defaultValue={110} />
                      </div>
                    </div>
                    <div className="mt-4">
                      <Label htmlFor="maxReuse">Max Reuse</Label>
                      <Input id="maxReuse" name="maxReuse" type="number" defaultValue={3} />
                    </div>
                  </div>
                  
                  <CardFooter className="px-0 gap-3 pt-6">
                    <Button 
                      type="submit" 
                      disabled={busy} 
                      className="btn-primary inline-flex items-center gap-2 flex-1"
                    >
                      {busy ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <Brain className="size-4" />
                          Create Compilation
                        </>
                      )}
                    </Button>
                    <Button 
                      type="reset" 
                      variant="outline" 
                      className="inline-flex items-center gap-2 hover:bg-muted/80" 
                      onClick={(e) => e.currentTarget.form?.reset()}
                    >
                      <RefreshCw className="size-4" /> Reset
                    </Button>
                  </CardFooter>
                </form>
              </CardContent>
            </Card>
          </div>

          <div className="col-span-12 lg:col-span-6 xl:col-span-6 2xl:col-span-6">
            <JobPanel
              jobId={jobId}
              status={job?.status}
              steps={progress}
              error={job?.error}
            />
          </div>

          <div className="col-span-12 lg:col-span-3 xl:col-span-3 2xl:col-span-3">
            {previewUrl ? (
              <Card className="lg:sticky lg:top-6 self-start enhanced-card fade-in">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div className="size-5 rounded bg-gradient-to-r from-green-400 to-blue-500 flex items-center justify-center">
                      <BadgeCheck className="size-3 text-white" />
                    </div>
                    Result
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <video src={previewUrl} controls className="video-frame w-full max-h-[75vh]" />
                    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                      <span className="text-sm text-muted-foreground">Video ready</span>
                      <a className="muted-link font-medium" href={previewUrl} download target="_blank" rel="noreferrer">Download video</a>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}


