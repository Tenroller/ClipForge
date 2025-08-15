import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { Loader2, BadgeCheck } from 'lucide-react'
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

export default function CreatorPage() {
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
  const [subtitlePositionRaw, setSubtitlePositionRaw] = useState<string>('center,bottom')
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<any>(null)
  const [lastRun, setLastRun] = useState<{ workflow: 'moneyprinter'; payload: any } | null>(null)

  // Persistence helpers
  function saveLastJob(partial: Partial<{ jobId: string; status: string; startedAt: number; payload: any }>) {
    try {
      const prev = JSON.parse(localStorage.getItem('creator:lastJob') || '{}')
      const next = { ...prev, ...partial, workflow: 'moneyprinter' }
      localStorage.setItem('creator:lastJob', JSON.stringify(next))
    } catch {}
  }
  function saveLastResult(result: any) {
    try {
      localStorage.setItem('creator:lastResult', JSON.stringify(result || {}))
    } catch {}
  }

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
      // Try restore previous session
      try {
        const lastJob = JSON.parse(localStorage.getItem('creator:lastJob') || 'null') as any
        const lastResult = JSON.parse(localStorage.getItem('creator:lastResult') || 'null') as any
        if (lastResult?.output) {
          const dl = `${API}/api/download?path=${encodeURIComponent(lastResult.output)}`
          setPreviewUrl(dl)
        } else if (lastResult?.output_dir) {
          // will be resolved by handlePreviewForJob when job finishes; best-effort here
        }
        if (lastJob?.jobId) {
          setJobId(lastJob.jobId)
          // Reconnect if not terminal
          const s = String(lastJob.status || '').toLowerCase()
          const isTerminal = ['done', 'error', 'cancelled'].includes(s)
          if (!isTerminal) {
            connectJobUpdates(lastJob.jobId)
          }
        }
      } catch {}
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
      useTikTokSubtitles: form.get('useTikTokSubtitles') === 'true',
      subtitleFont: String(form.get('subtitleFont') || 'Arial'),
      subtitleFontSize: Number(form.get('subtitleFontSize') || 48),
      subtitleDefaultColor: String(form.get('subtitleDefaultColor') || '#FFFFFF'),
      subtitleHighlightColor: String(form.get('subtitleHighlightColor') || '#FFFF00'),
      subtitleStrokeColor: String(form.get('subtitleStrokeColor') || '#000000'),
      subtitleBackgroundColor: String(form.get('subtitleBackgroundColor') || '#000000'),
      subtitleStrokeWidth: Number(form.get('subtitleStrokeWidth') || 2),
      subtitleBackgroundOpacity: Number(form.get('subtitleBackgroundOpacity') || 0.6),
      subtitlePaddingX: Number(form.get('subtitlePaddingX') || 16),
      subtitlePaddingY: Number(form.get('subtitlePaddingY') || 12),
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
          // persist status
          saveLastJob({ jobId: id, status: data.status })
          // persist result when available
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

  const progress = useMemo(() => {
    const current = (job?.step || (job?.status === 'done' ? 'done' : 'init')) as string
    const hasResult = !!previewUrl || !!(job as any)?.result?.output || !!(job as any)?.result?.output_dir
    const includeFetchMusic = !!lastRun?.payload?.useMusic && !!lastRun?.payload?.zipUrl
    const steps: string[] = includeFetchMusic ? ([ 'validate_env', 'fetch_music', ...stepOrderMoneyPrinterBase.slice(1) ]) : ([...stepOrderMoneyPrinterBase])
    const idxBase = steps.indexOf(current)
    const idx = hasResult || job?.status === 'done' ? steps.length - 1 : Math.max(0, idxBase - 1)
    return steps.map(s => ({ 
      key: s, 
      label: labelForStep(s), 
      done: idx >= steps.indexOf(s),
      active: !hasResult && job?.status !== 'done' && s === current
    }))
  }, [job?.step, job?.status, previewUrl, lastRun?.payload])

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
      case 'done': return 'Done'
      default: return step
    }
  }

  return (
    <div className="container-page fade-in max-w-[1760px]">
      <div aria-live="polite" className="sr-only">
        {job ? `Job ${jobId || ''} status ${job.status}${job.step ? `, step ${job.step}` : ''}` : 'No active job'}
      </div>

      <div className="slide-in">
        <div className="grid grid-cols-12 gap-4 lg:gap-5 xl:gap-6 items-start grid-layout-fix">
          <div className="col-span-12 lg:col-span-4 xl:col-span-4 2xl:col-span-4">
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
              formId="moneyprinter-form"
              onReset={() => {
                setSubtitleColor('#FFFF00')
                setSubtitlePosition('center,bottom')
                setVoice('af_bella')
              }}
            />
          </div>

          <div className="col-span-12 lg:col-span-3 xl:col-span-3 2xl:col-span-3 lg:sticky lg:top-6 self-start space-y-4" aria-label="Preview and subtitle controls">
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

          <div className="col-span-12 lg:col-span-5 xl:col-span-4 2xl:col-span-4 lg:sticky lg:top-6 self-start">
            <JobPanel
              jobId={jobId}
              status={job?.status}
              steps={progress}
              error={job?.error}
            />
          </div>
          {previewUrl ? (
            <Card className="col-span-12 lg:col-span-4 xl:col-span-3 lg:sticky lg:top-6 self-start enhanced-card fade-in">
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
      </div>
    </div>
  )
}


