import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import MoneyPrinterForm from '@/components/components/moneyprinter-form'
import PreviewPanel from '@/components/components/preview-panel'
import { MultiJobPanel } from '@/components/MultiJobPanel'
import ResultPanel from '@/components/ResultPanel'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function CreatorPage() {
  const [busy, setBusy] = useState(false)
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const [aiModel, setAiModel] = useState<string>('gemini-2.0-flash')
  const [models, setModels] = useState<string[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [voice, setVoice] = useState<string>('af_bella')
  const [subtitleColor, setSubtitleColor] = useState<string>('#FFFF00')
  const [subtitlePosition, setSubtitlePosition] = useState<string>('center,bottom')
  const [subtitlePositionRaw, setSubtitlePositionRaw] = useState<string>('center,bottom')

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
          console.log(`CreatorPage: Cleaned up ${removedCount} non-existent jobs`)
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
      const res = await fetch(`${API}/api/moneyprinter/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      
      // Add job to the manager
      console.log('CreatorPage: Adding job to manager', data.jobId, payload);
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
        {/* Job Queue - Show only when there are jobs */}
        {jobManager.jobs.length > 0 && (
          <MultiJobPanel
            jobs={jobManager.jobs}
            onViewResult={handleViewResult}
            onRemoveJob={jobManager.removeJob}
            onClearCompleted={jobManager.clearCompletedJobs}
          />
        )}

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
                  setSubtitleColor('#FFFF00')
                  setSubtitlePosition('center,bottom')
                  setVoice('af_bella')
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


