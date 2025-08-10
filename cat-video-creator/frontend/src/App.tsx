import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/components/ui/tabs'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { Input } from '@/components/components/ui/input'
import { Label } from '@/components/components/ui/label'
import { Textarea } from '@/components/components/ui/textarea'
import { Loader2, BadgeCheck, AlertTriangle, Clapperboard, Brain, RefreshCw } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/components/ui/select'
import { normalizeSubtitlesPosition } from './components/SubtitlePreview'
import ThemeToggle from './components/ThemeToggle'
import MoneyPrinterForm from '@/components/components/moneyprinter-form'
import PreviewPanel from '@/components/components/preview-panel'
import JobPanel from '@/components/components/job-panel'

type Job = {
  status: string
  step?: string
  result?: any
  error?: string
}

const API = 'http://localhost:8080'

export default function App() {
  const [workflow, setWorkflow] = useState<'moneyprinter' | 'brainrot'>('moneyprinter')
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [aiModel, setAiModel] = useState<string>('gemini-2.0-flash')
  const [models, setModels] = useState<string[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [voice, setVoice] = useState<string>('af_bella')
  const [subtitleColor, setSubtitleColor] = useState<string>('#FFFF00')
  const [subtitlePosition, setSubtitlePosition] = useState<string>('center,bottom')
  // Supports: grid ("left,top"), pct ("pct:x,y"), px ("px:x,y"). Persist raw string here.
  const [subtitlePositionRaw, setSubtitlePositionRaw] = useState<string>('center,bottom')
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<any>(null)
  const [lastRun, setLastRun] = useState<{ workflow: 'moneyprinter' | 'brainrot'; payload: any } | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const [m, v] = await Promise.all([
          fetch(`${API}/api/models`).then(r => r.json()),
          fetch(`${API}/api/voices`).then(r => r.json()),
        ])
        if (Array.isArray(m?.models)) setModels(m.models)
        if (Array.isArray(v?.voices)) setVoices(v.voices)
      } catch {
        // ignore
      }
    })()
  }, [])

  async function startMoneyPrinter(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
      const payload = {
      videoSubject: String(form.get('videoSubject') || ''),
      aiModel: aiModel || 'gemini-2.0-flash',
      paragraphNumber: Number(form.get('paragraphNumber') || 1),
      threads: Number(form.get('threads') || 2),
        subtitlesPosition: String(subtitlePositionRaw || subtitlePosition),
      color: String(form.get('color') || subtitleColor),
      useMusic: !!form.get('useMusic'),
      zipUrl: String(form.get('zipUrl') || '' ) || null,
      automateYoutubeUpload: !!form.get('automateYoutubeUpload'),
      useGPU: true,
      voice: voice || 'af_bella',
      customPrompt: String(form.get('customPrompt') || '') || null,
    }
    if (!payload.videoSubject) return toast.error('Subject is required')
    setBusy(true)
    try {
      const res = await fetch(`${API}/api/moneyprinter/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setJobId(data.jobId)
      toast.success('Job started')
      connectJobUpdates(data.jobId)
      setLastRun({ workflow: 'moneyprinter', payload })
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

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
    // Cleanup existing
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
        } catch {}
        // Send a small ping to keep connection alive
        try { ws.send('ack') } catch {}
      }
      ws.onopen = () => {
        // Initial ping so backend receive loop continues
        try { ws.send('hello') } catch {}
      }
      ws.onerror = () => {
        // Fallback to polling on error
        startPollingFallback(id)
      }
      ws.onclose = () => {
        // If job not finished, fallback to polling
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

  const stepOrderMoneyPrinterBase = [
    'validate_env',
    'script_generation',
    'search_terms',
    'stock_download',
    'tts',
    'subtitles',
    'compose_video',
    'done',
  ] as const

  const stepOrderBrainrot = [
    'process_video',
    'generate_compilations',
    'done',
  ] as const

  const progress = useMemo(() => {
    const current = (job?.step || (job?.status === 'done' ? 'done' : 'init')) as string
    const hasResult = !!previewUrl || !!(job as any)?.result?.output || !!(job as any)?.result?.output_dir
    if ((lastRun?.workflow || workflow) === 'brainrot') {
      const idxBase = stepOrderBrainrot.indexOf(current as any)
      const idx = hasResult || job?.status === 'done' ? stepOrderBrainrot.length - 1 : idxBase
      return stepOrderBrainrot.map(s => ({ key: s, label: labelForStep(s), done: idx >= stepOrderBrainrot.indexOf(s) }))
    }
    const includeFetchMusic = !!lastRun?.payload?.useMusic && !!lastRun?.payload?.zipUrl
    const steps: string[] = includeFetchMusic ? ([ 'validate_env', 'fetch_music', ...stepOrderMoneyPrinterBase.slice(1) ]) : ([...stepOrderMoneyPrinterBase])
    const idxBase = steps.indexOf(current)
    const idx = hasResult || job?.status === 'done' ? steps.length - 1 : idxBase
    return steps.map(s => ({ key: s, label: labelForStep(s), done: idx >= steps.indexOf(s) }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.step, job?.status, workflow, lastRun?.workflow, previewUrl])

  function labelForStep(step: string) {
    switch (step) {
      case 'validate_env': return 'Validate Env'
      case 'fetch_music': return 'Fetch Music'
      case 'script_generation': return 'Script Generation'
      case 'search_terms': return 'Search Terms'
      case 'stock_download': return 'Stock Download'
      case 'tts': return 'TTS'
      case 'subtitles': return 'Subtitles'
      case 'compose_video': return 'Compose Video'
      case 'process_video': return 'Process Video'
      case 'generate_compilations': return 'Generate Compilations'
      case 'done': return 'Done'
      default: return step
    }
  }

  return (
    <div className="container-page">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="section-title flex items-center gap-2">
            <Clapperboard className="size-6" /> AI Video Creator
          </h1>
          <p className="section-subtitle">Create videos purrely with AI or from compilations</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-muted-foreground">API: {API.replace('http://', '')}</div>
          <ThemeToggle />
        </div>
      </header>
      <div aria-live="polite" className="sr-only">
        {job ? `Job ${jobId || ''} status ${job.status}${job.step ? `, step ${job.step}` : ''}` : 'No active job'}
      </div>

      <Tabs defaultValue={workflow} onValueChange={(v) => setWorkflow(v as any)}>
        <TabsList className="mb-4">
          <TabsTrigger value="moneyprinter" className="flex items-center gap-2">
            <BadgeCheck className="size-4" /> Create videos purrely with AI
          </TabsTrigger>
          <TabsTrigger value="brainrot" className="flex items-center gap-2">
            <Brain className="size-4" /> Create videos from compilations
          </TabsTrigger>
        </TabsList>

        <TabsContent value="moneyprinter">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
            <MoneyPrinterForm
              models={models}
              aiModel={aiModel}
              onChangeAiModel={setAiModel}
              voices={voices}
              voice={voice}
              onChangeVoice={setVoice}
              subtitleColor={subtitleColor}
              onChangeSubtitleColor={setSubtitleColor}
              subtitlesPosition={subtitlePosition}
              apiBase={API}
              busy={busy}
              onSubmit={startMoneyPrinter}
              onReset={() => {
                setSubtitleColor('#FFFF00')
                setSubtitlePosition('center,bottom')
                setVoice('af_bella')
              }}
            />

            <div className="lg:sticky lg:top-6 self-start space-y-6" aria-label="Preview and subtitle controls">
              <PreviewPanel
                position={subtitlePosition.replace(',', '-') as any}
                onChangePosition={(p) => {
                  const grid = String(p).replace('-', ',')
                  setSubtitlePosition(grid)
                  setSubtitlePositionRaw(grid)
                }}
                previewUrl={previewUrl}
                color={subtitleColor}
                positionRaw={subtitlePositionRaw}
                onChangePositionRaw={(raw) => setSubtitlePositionRaw(raw)}
              />
            </div>

            <div className="lg:sticky lg:top-6 self-start lg:col-start-3">
               <JobPanel
                jobId={jobId}
                status={job?.status}
                steps={progress}
                error={job?.error}
              />
            </div>
            {previewUrl ? (
              <Card className="lg:sticky lg:top-6 self-start lg:col-start-4">
                <CardHeader>
                  <CardTitle>Result</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <video src={previewUrl} controls className="w-full max-h-[75vh] rounded border border-zinc-800" />
                    <div>
                      <a className="text-xs underline text-blue-300" href={previewUrl} download target="_blank" rel="noreferrer">Download video</a>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="brainrot">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
            <Card>
              <CardHeader>
                <CardTitle>Create videos from compilations</CardTitle>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={startBrainrot} aria-describedby="br-help">
                  <div>
                    <Label htmlFor="youtubeUrl">YouTube URL</Label>
                    <Input id="youtubeUrl" name="youtubeUrl" placeholder="https://youtu.be/..." required aria-required="true" />
                    <p id="br-help" className="mt-1 text-xs text-muted-foreground">Paste a single video URL. Required.</p>
                  </div>
                  <div className="grid-3">
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
                  <div>
                    <Label htmlFor="maxReuse">Max Reuse</Label>
                    <Input id="maxReuse" name="maxReuse" type="number" defaultValue={3} />
                  </div>
                  <CardFooter className="px-0 gap-2">
                    <Button type="submit" disabled={busy} className="inline-flex items-center gap-2">
                      {busy ? (<><Loader2 className="animate-spin" /> Running…</>) : 'Create videos from compilations'}
                    </Button>
                    <Button type="reset" variant="outline" className="inline-flex items-center gap-2" onClick={(e) => e.currentTarget.form?.reset()}>
                      <RefreshCw className="size-4" /> Reset
                    </Button>
                  </CardFooter>
                </form>
              </CardContent>
            </Card>

            {/* Column 2 intentionally left for preview (not used in Brainrot) */}

            <Card className="lg:sticky lg:top-6 self-start lg:col-start-3">
              <CardHeader>
                <CardTitle>Job</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">ID: {jobId || '—'}</div>
                <div className="text-sm text-muted-foreground flex items-center gap-2">Status: {job?.status || '—'}</div>
                <div className="text-sm text-muted-foreground">Step: {job?.step || '—'}</div>
                <div className="mt-3">
                  {(() => {
                    const total = progress.length || 1
                    const completed = progress.filter(p => p.done).length
                    const percent = Math.round((completed / total) * 100)
                    return (
                      <div className="w-full h-2 rounded bg-zinc-800" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Job progress">
                        <div className="h-full rounded bg-primary" style={{ width: `${percent}%` }} />
                      </div>
                    )
                  })()}
                </div>
                <div className="mt-3 space-y-2">
                  {progress.map(p => (
                    <label key={p.key} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={!!p.done} readOnly className="accent-green-500" />
                      <span>{p.label}</span>
                    </label>
                  ))}
                </div>
                {job?.error && (
                  <div className="mt-3 text-red-400 text-sm flex items-center gap-2"><AlertTriangle className="size-4" /> {job.error}</div>
                )}
                {job?.result && (
                  <pre className="mt-3 text-xs bg-black/40 p-3 rounded border border-zinc-800 overflow-auto max-h-80">{JSON.stringify(job.result, null, 2)}</pre>
                )}
              </CardContent>
            </Card>
            {previewUrl ? (
              <Card className="lg:sticky lg:top-6 self-start lg:col-start-4">
                <CardHeader>
                  <CardTitle>Result</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <video src={previewUrl} controls className="w-full max-h-[75vh] rounded border border-zinc-800" />
                    <div>
                      <a className="text-xs underline text-blue-300" href={previewUrl} download target="_blank" rel="noreferrer">Download video</a>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </TabsContent>
      </Tabs>

      {/* Jobs panel moved to right columns above */}
    </div>
  )
}


