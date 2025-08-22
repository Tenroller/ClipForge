import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Input } from '@/components/components/ui/input'
import { Label } from '@/components/components/ui/label'
import { Button } from '@/components/components/ui/button'
import { Switch } from '@/components/components/ui/switch'
import { Loader2, Brain, HelpCircle, Cpu } from 'lucide-react'    
import { MultiJobPanel } from '@/components/MultiJobPanel'
import ResultPanel from '@/components/ResultPanel'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function CompilationsPage() {
  const [busy, setBusy] = useState(false)
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const [useGpu, setUseGpu] = useState(true)

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
          console.log(`CompilationsPage: Cleaned up ${removedCount} non-existent jobs`)
        }
      } catch (e) {
        console.warn('Failed to cleanup legacy jobs:', e)
      }
    }
    
    cleanupLegacy()
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
    
    if (!payload.youtubeUrl) {
      toast.error('YouTube URL is required')
      return
    }

    setBusy(true)
    try {
      const res = await fetch(`${API}/api/brainrot/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      
      // Add job to the manager
      jobManager.addJob(data.jobId, 'brainrot', payload)
      toast.success('Compilation job started successfully')
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
          ? `${jobManager.getActiveJobs().length} active compilation jobs`
          : 'No active compilation jobs'
        }
      </div>

      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-green-600 to-blue-600 bg-clip-text text-transparent">
          Video Compilation Generator
        </h1>
        <p className="text-muted-foreground mt-2">
          Create engaging compilation videos from YouTube content
        </p>
      </div>

      <div className="slide-in space-y-8">
        {/* Job Queue - Show only when there are jobs */}
        {jobManager.jobs.filter(j => j.workflow === 'brainrot').length > 0 && (
          <MultiJobPanel
            jobs={jobManager.jobs.filter(j => j.workflow === 'brainrot')}
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

        {/* Main Content - Hide when showing results */}
        {!selectedResult && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Form Section */}
            <Card className="enhanced-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-gradient-to-r from-green-500 to-blue-600 flex items-center justify-center">
                    <Brain className="size-4 text-white" />
                  </div>
                  Brainrot Generator
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Transform YouTube videos into TikTok-style compilations
                </p>
              </CardHeader>
              <CardContent>
                <form onSubmit={startBrainrot} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="youtubeUrl">YouTube URL</Label>
                    <Input
                      id="youtubeUrl"
                      name="youtubeUrl"
                      type="url"
                      placeholder="https://youtube.com/watch?v=..."
                      required
                      className="transition-all duration-200"
                    />
                    <p className="text-xs text-muted-foreground">
                      Enter a YouTube video URL to create compilations from
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="numCompilations">
                        Compilations
                        <HelpCircle className="inline size-3 ml-1 opacity-60" />
                      </Label>
                      <Input
                        id="numCompilations"
                        name="numCompilations"
                        type="number"
                        min="1"
                        max="10"
                        defaultValue="1"
                        className="transition-all duration-200"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="maxReuse">
                        Max Reuse
                        <HelpCircle className="inline size-3 ml-1 opacity-60" />
                      </Label>
                      <Input
                        id="maxReuse"
                        name="maxReuse"
                        type="number"
                        min="1"
                        max="10"
                        defaultValue="3"
                        className="transition-all duration-200"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="minDuration">Min Duration (seconds)</Label>
                      <Input
                        id="minDuration"
                        name="minDuration"
                        type="number"
                        min="10"
                        max="3600"
                        defaultValue="60"
                        className="transition-all duration-200"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="maxDuration">Max Duration (seconds)</Label>
                      <Input
                        id="maxDuration"
                        name="maxDuration"
                        type="number"
                        min="10"
                        max="3600"
                        defaultValue="110"
                        className="transition-all duration-200"
                      />
                    </div>
                  </div>

                  {/* Local GPU Toggle */}
                  <div className="flex items-center justify-between p-4 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      {useGpu ? (
                        <Cpu className="size-5 text-green-500" />
                      ) : (
                        <Cpu className="size-5 text-gray-500" />
                      )}
                      <div>
                        <Label htmlFor="use-gpu-brainrot" className="font-medium">
                          {useGpu ? 'GPU Acceleration' : 'CPU Processing'}
                        </Label>
                        <p className="text-xs text-muted-foreground">
                          {useGpu 
                            ? 'Using local GPU for faster video processing'
                            : 'Using CPU for video processing (slower)'
                          }
                        </p>
                      </div>
                    </div>
                    <Switch
                      id="use-gpu-brainrot"
                      checked={useGpu}
                      onCheckedChange={setUseGpu}
                    />
                  </div>

                  <Button
                    type="submit"
                    disabled={busy}
                    className="w-full relative transition-all duration-200"
                  >
                    {busy ? (
                      <>
                        <Loader2 className="size-4 mr-2 animate-spin" />
                        Starting Compilation...
                      </>
                    ) : (
                      <>
                        <Brain className="size-4 mr-2" />
                        Generate Compilation
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Info Panel */}
            <Card className="enhanced-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-gradient-to-r from-orange-500 to-red-600 flex items-center justify-center">
                    <HelpCircle className="size-4 text-white" />
                  </div>
                  How It Works
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-4 text-sm text-muted-foreground">
                  <div className="flex gap-3">
                    <div className="size-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs font-medium text-blue-600 dark:text-blue-400">1</span>
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Extract Content</p>
                      <p>Download and analyze the YouTube video for interesting segments</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-3">
                    <div className="size-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs font-medium text-green-600 dark:text-green-400">2</span>
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Create Clips</p>
                      <p>Generate multiple compilation videos with the specified duration</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-3">
                    <div className="size-6 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs font-medium text-purple-600 dark:text-purple-400">3</span>
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Optimize Format</p>
                      <p>Format videos for social media platforms like TikTok and Instagram</p>
                    </div>
                  </div>
                </div>
                
                <div className="mt-6 p-3 rounded-lg bg-muted/50 border">
                  <p className="text-xs text-muted-foreground">
                    <strong>Tip:</strong> Use longer source videos (10+ minutes) for better compilation variety
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
