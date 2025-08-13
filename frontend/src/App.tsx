import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/components/ui/tabs'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/components/ui/card'
import { Button } from '@/components/components/ui/button'
import { Input } from '@/components/components/ui/input'
import { Label } from '@/components/components/ui/label'
import { Textarea } from '@/components/components/ui/textarea'
import { Loader2, BadgeCheck, AlertTriangle, Clapperboard, Brain, RefreshCw, HelpCircle } from 'lucide-react'
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

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

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
      useGPU: !!form.get('useGPU'),
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
      // Only mark steps as done if they're completed (before current step) or if job is fully done
      const idx = hasResult || job?.status === 'done' ? stepOrderBrainrot.length - 1 : Math.max(0, idxBase - 1)
      return stepOrderBrainrot.map(s => ({ 
        key: s, 
        label: labelForStep(s), 
        done: idx >= stepOrderBrainrot.indexOf(s),
        active: !hasResult && job?.status !== 'done' && s === current
      }))
    }
    const includeFetchMusic = !!lastRun?.payload?.useMusic && !!lastRun?.payload?.zipUrl
    const steps: string[] = includeFetchMusic ? ([ 'validate_env', 'fetch_music', ...stepOrderMoneyPrinterBase.slice(1) ]) : ([...stepOrderMoneyPrinterBase])
    const idxBase = steps.indexOf(current)
    // Only mark steps as done if they're completed (before current step) or if job is fully done
    const idx = hasResult || job?.status === 'done' ? steps.length - 1 : Math.max(0, idxBase - 1)
    return steps.map(s => ({ 
      key: s, 
      label: labelForStep(s), 
      done: idx >= steps.indexOf(s),
      active: !hasResult && job?.status !== 'done' && s === current
    }))
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
    <div className="container-page fade-in">
      <header className="mb-8 rounded-2xl glass-header px-6 py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center shadow-lg">
              <Clapperboard className="size-6 text-white" />
            </div>
            <div>
              <h1 className="section-title flex items-center gap-2 text-2xl">
                AI Video Creator
              </h1>
              <p className="section-subtitle mt-1">Create stunning videos with AI or compilations</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 border border-border/50">
              <div className="size-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-xs font-medium text-muted-foreground">API: {API.replace('http://', '')}</span>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <div aria-live="polite" className="sr-only">
        {job ? `Job ${jobId || ''} status ${job.status}${job.step ? `, step ${job.step}` : ''}` : 'No active job'}
      </div>

      <Tabs defaultValue={workflow} onValueChange={(v) => setWorkflow(v as any)}>
        <TabsList className="mb-6 h-12 bg-muted/30 backdrop-blur border border-border/50">
          <TabsTrigger value="moneyprinter" className="flex items-center gap-2 h-10 px-6 data-[state=active]:bg-background/80 data-[state=active]:shadow-sm">
            <BadgeCheck className="size-4" /> Create videos with AI
          </TabsTrigger>
          <TabsTrigger value="brainrot" className="flex items-center gap-2 h-10 px-6 data-[state=active]:bg-background/80 data-[state=active]:shadow-sm">
            <Brain className="size-4" /> Create from compilations
          </TabsTrigger>
        </TabsList>

        <TabsContent value="moneyprinter" className="slide-in">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 lg:gap-6 items-start grid-layout-fix">
            <div className="lg:col-start-1">
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
            </div>

            <div className="lg:col-start-2 lg:sticky lg:top-6 self-start space-y-6" aria-label="Preview and subtitle controls">
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

            <div className="lg:col-start-3 lg:sticky lg:top-6 self-start">
               <JobPanel
                jobId={jobId}
                status={job?.status}
                steps={progress}
                error={job?.error}
              />
            </div>
            {previewUrl ? (
              <Card className="lg:sticky lg:top-6 self-start lg:col-start-4 enhanced-card fade-in">
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
                    <video src={previewUrl} controls className="video-frame w-full max-h-[60vh] lg:max-h-[75vh]" />
                    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                      <span className="text-sm text-muted-foreground">Video ready</span>
                      <a className="muted-link font-medium" href={previewUrl} download target="_blank" rel="noreferrer">Download video</a>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="brainrot" className="slide-in">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 lg:gap-6 items-start">
            <Card className="enhanced-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                    <Brain className="size-4 text-white" />
                  </div>
                  Create from compilations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form className="space-y-6" onSubmit={startBrainrot} aria-describedby="br-help">
                  <div className="form-section">
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
                  
                  <div className="form-section">
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

            {/* Column 2 intentionally left for preview (not used in Brainrot) */}

            <JobPanel
              jobId={jobId}
              status={job?.status}
              steps={progress}
              error={job?.error}
            />
            {previewUrl ? (
              <Card className="lg:sticky lg:top-6 self-start lg:col-start-4 enhanced-card fade-in">
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
        </TabsContent>
      </Tabs>

      {/* Jobs panel moved to right columns above */}
    </div>
  )
}


