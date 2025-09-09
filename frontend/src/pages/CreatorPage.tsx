import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import MoneyPrinterForm from '@/components/components/moneyprinter-form'
import PreviewPanel from '@/components/components/preview-panel'
import ResultPanel from '@/components/ResultPanel'
import JobStartedNotification from '@/components/JobStartedNotification'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'
import { generateMoneyPrinterVideo } from '@/lib/api'

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function CreatorPage() {
  const [busy, setBusy] = useState(false)
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const [aiModel, setAiModel] = useState<string>('gemini-2.0-flash')
  const [models, setModels] = useState<string[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [voice, setVoice] = useState<string>('af_bella')
  const [subtitleColor, setSubtitleColor] = useState<string>('#FFFFFF')  // Changed to white
  const [subtitlePosition, setSubtitlePosition] = useState<string>('center,bottom')
  const [subtitlePositionRaw, setSubtitlePositionRaw] = useState<string>('center,bottom')
  
  // 3D Blue Shadow Colors for Enhanced Subtitles
  const [shadowLayersCount, setShadowLayersCount] = useState<number>(4)  // Number of shadow layers (2, 3, or 4)
  const [shadowLayer1Color, setShadowLayer1Color] = useState<string>('#4A90E2')
  const [shadowLayer2Color, setShadowLayer2Color] = useState<string>('#357ABD')
  const [shadowLayer3Color, setShadowLayer3Color] = useState<string>('#2E5F8A')
  const [shadowLayer4Color, setShadowLayer4Color] = useState<string>('#1E3F5A')

  const jobManager = useJobManager()

  // Clean up any legacy job data on component mount
  useEffect(() => {
    const cleanupLegacy = async () => {
      try {
        // Clean up legacy localStorage entries
        await jobManager.cleanupLegacyJobs()
        
        // Validate all current jobs to remove any 404s
        const removedCount = await jobManager.validateAllJobs()
        if (removedCount > 0) {
          devLog('CreatorPage: Cleaned up', removedCount, 'non-existent jobs')
        }
      } catch (e) {
        console.warn('Failed to cleanup legacy jobs:', e)
      }
    }
    
    cleanupLegacy()
  }, [])

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

    if (!payload.videoSubject) {
      toast.error('Subject is required')
      return
    }

    setBusy(true)
    try {
      const data = await generateMoneyPrinterVideo(payload)

      // Add job to the manager
      devLog('CreatorPage: Adding job to manager', data.jobId, payload);
      jobManager.addJob(data.jobId, 'moneyprinter', payload)
      toast.success('Job started successfully')
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleViewResult = (job: ManagedJob) => {
    setSelectedResult(job)
  }

  const handleCloseResult = () => {
    setSelectedResult(null)
  }

  return (
    <div className="container-page-wide fade-in">
      <div aria-live="polite" className="sr-only">
        {jobManager.hasActiveJobs() 
          ? `${jobManager.getActiveJobs().length} active jobs running`
          : 'No active jobs'
        }
      </div>

      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          AI Video Generator
        </h1>
        <p className="text-muted-foreground mt-2">
          Create engaging videos with AI-generated content and customizable subtitles
        </p>
      </div>

      <div className="slide-in space-y-8">
        {/* Show active jobs as simple notifications with auto-redirect */}
        {(() => {
          const activeJobs = jobManager.jobs.filter(j => j.workflow === 'moneyprinter' && ['queued', 'running'].includes(j.status))
          return activeJobs.map(job => (
            <JobStartedNotification 
              key={job.id}
              jobId={job.id}
              workflow={job.workflow}
              autoRedirect={true}
              redirectDelay={3000}
            />
          ))
        })()}

        {/* Result Panel - Show when a result is selected */}
        {selectedResult && (
          <ResultPanel
            job={selectedResult}
            onClose={handleCloseResult}
          />
        )}

        {/* Main Content Grid - Hide when showing results */}
        {!selectedResult && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
            {/* Form Section - Left Side */}
            <div className="lg:col-span-4 xl:col-span-4 space-y-6">
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
                  setSubtitleColor('#FFFFFF')  // Changed to white
                  setSubtitlePosition('center,bottom')
                  setVoice('af_bella')
                  setShadowLayersCount(4)  // Professional (4 layers)
                  setShadowLayer1Color('#4A90E2')
                  setShadowLayer2Color('#357ABD')
                  setShadowLayer3Color('#2E5F8A')
                  setShadowLayer4Color('#1E3F5A')
                }}
              />
            </div>

            {/* Right Side - Preview */}
            <div className="lg:col-span-8 xl:col-span-8 space-y-6">
              <div className="space-y-4" aria-label="Preview and subtitle controls">
                <PreviewPanel
                  position={subtitlePosition.replace(',', '-') as any}
                  onChangePosition={(p) => {
                    const grid = String(p).replace('-', ',')
                    setSubtitlePosition(grid)
                    setSubtitlePositionRaw(grid)
                  }}
                  previewUrl={undefined} // We'll handle preview in the result panel now
                  color={subtitleColor}
                  positionRaw={subtitlePositionRaw}
                  shadowLayersCount={shadowLayersCount}
                  shadowLayer1Color={shadowLayer1Color}
                  shadowLayer2Color={shadowLayer2Color}
                  shadowLayer3Color={shadowLayer3Color}
                  shadowLayer4Color={shadowLayer4Color}
                  onChangePositionRaw={(raw) => setSubtitlePositionRaw(raw)}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


