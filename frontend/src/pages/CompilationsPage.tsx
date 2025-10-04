import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/components/ui/card'
import { Input } from '@/components/components/ui/input'
import { Label } from '@/components/components/ui/label'
import { Button } from '@/components/components/ui/button'
import { Switch } from '@/components/components/ui/switch'
import { FaSpinner, FaBrain, FaQuestionCircle, FaMicrochip, FaVideo } from 'react-icons/fa'
import ResultPanel from '@/components/ResultPanel'
import JobStartedNotification from '@/components/JobStartedNotification'
import { useJobManager } from '@/hooks/useJobManager'
import { type ManagedJob } from '@/lib/jobManager'
import { GeneratedVideosPanel } from '@/components/GeneratedVideosPanel'
import { generateBrainrotVideo } from '@/lib/api'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

// Development-only logging
const devLog = (message: string, ...args: any[]) => {
  if (import.meta.env.DEV) {
    console.log(message, ...args)
  }
}



export default function CompilationsPage() {
  const [busy, setBusy] = useState(false)
  const [selectedResult, setSelectedResult] = useState<ManagedJob | null>(null)
  const [useGpu, setUseGpu] = useState(true)
  const [isUnlimited, setIsUnlimited] = useState(false)
  const [generateNoBackground, setGenerateNoBackground] = useState(true)
  const [blurredPillarboxThreshold, setBlurredPillarboxThreshold] = useState([0.1])
  
  // Video input method selection
  const [inputMethod, setInputMethod] = useState<'youtube' | 'upload'>('youtube')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const jobManager = useJobManager()

  // File upload function
    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadedFile(file);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API}/api/upload-video`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setUploadedFileId(data.file_id);
      setUploadedFilePath(data.file_path);
      toast.success('Video uploaded successfully');
    } catch (error: any) {
      toast.error(`Upload failed: ${error.message}`);
      setUploadedFile(null);
      setUploadedFileId(null);
      setUploadedFilePath(null);
    } finally {
      setIsUploading(false);
    }
  };

  // Clean up any legacy job data on component mount
  useEffect(() => {
    const cleanupLegacy = async () => {
      try {
        // Clean up legacy localStorage entries
        await jobManager.cleanupLegacyJobs()
        
        // Validate all current jobs to remove any 404s
        const removedCount = await jobManager.validateAllJobs()
        if (removedCount > 0) {
          devLog(`CompilationsPage: Cleaned up ${removedCount} non-existent jobs`)
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
      youtubeUrl: inputMethod === 'youtube' ? String(form.get('youtubeUrl') || '') : undefined,
      uploadedVideoPath: inputMethod === 'upload' ? uploadedFilePath : undefined,
      numCompilations: Number(form.get('numCompilations') || 1),
      minDuration: Number(form.get('minDuration') || 20),
      maxDuration: Number(form.get('maxDuration') || 40),
      maxReuse: Number(form.get('maxReuse') || 3),
      unlimited: isUnlimited,
      generateNoBackground: generateNoBackground,
      blurredPillarboxThreshold: blurredPillarboxThreshold[0],
    }

    // Validate that either YouTube URL or uploaded file is provided
    if (inputMethod === 'youtube' && !payload.youtubeUrl) {
      toast.error('YouTube URL is required')
      return
    }
    
    if (inputMethod === 'upload' && !uploadedFilePath) {
      toast.error('Please upload a video file first')
      return
    }

    setBusy(true)
    try {
      const data = await generateBrainrotVideo(payload)

      // Add job to the manager
      console.log('CompilationsPage: Adding job to manager:', data.jobId, payload);
      jobManager.addJob(data.jobId, 'brainrot', payload)
      console.log('CompilationsPage: Job added, current jobs:', jobManager.jobs.length);
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

  // Get completed brainrot jobs with generated videos
  const completedBrainrotJobs = jobManager.jobs.filter(job => 
    job.workflow === 'brainrot' && 
    job.status === 'done' && 
    job.result?.generated_videos
  )

  // Get the most recent completed job with videos
  const latestCompletedJob = completedBrainrotJobs.length > 0 
    ? completedBrainrotJobs.sort((a, b) => 
        (b.result?.duration_seconds || 0) - (a.result?.duration_seconds || 0)
      )[0] 
    : null

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
        {/* Show active jobs as simple notifications with auto-redirect */}
        {(() => {
          const activeJobs = jobManager.jobs.filter(j => j.workflow === 'brainrot' && ['queued', 'running'].includes(j.status))
          return activeJobs.map(job => (
            <JobStartedNotification 
              key={job.id}
              jobId={job.id}
              workflow={job.workflow}
              autoRedirect={job.isNewlyCreated === true}
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

        {/* Generated Videos Panel - Show when there are completed jobs with videos or jobs in progress */}
        {(() => {
          const brainrotJobs = jobManager.jobs.filter(j => j.workflow === 'brainrot')
          const activeJob = brainrotJobs.find(j => j.status === 'running' || j.status === 'queued')
          const completedJobWithVideos = brainrotJobs.find(j =>
            j.status === 'done' && j.result?.generated_videos
          )

          // Show panel if there's an active job or completed job with videos
          const shouldShowPanel = activeJob || completedJobWithVideos

          if (!shouldShowPanel) return null

          // Determine which job data to use
          const displayJob = completedJobWithVideos || activeJob
          const videos = displayJob?.result?.generated_videos || []
          const isGenerating = displayJob?.status === 'running' || displayJob?.status === 'queued'

          // Get numCompilations from the job payload
          const numCompilations = displayJob ? (displayJob as any).payload?.numCompilations || 0 : 0
          const isUnlimited = displayJob ? (displayJob as any).payload?.unlimited || false : false
          const expectedVideos = displayJob?.result?.expected_videos || (isUnlimited ? null : (numCompilations * 2))

          return (
            <GeneratedVideosPanel
              videos={videos}
              totalSizeMb={displayJob?.result?.total_size_mb || 0}
              compilationTypes={displayJob?.result?.compilation_types || { normal: 0, tts: 0, total: 0 }}
              numCompilations={numCompilations}
              expectedVideos={expectedVideos}
              isGenerating={isGenerating}
            />
          )
        })()}

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
                    <FaBrain className="size-4 text-white" />
                  </div>
                  Brainrot Generator
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Transform YouTube videos into TikTok-style compilations
                </p>
              </CardHeader>
              <CardContent>
                <form onSubmit={startBrainrot} className="space-y-4">
                  {/* Input Method Selection */}
                  <div className="space-y-3">
                    <Label>Video Source</Label>
                    <div className="flex gap-4">
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="radio"
                          name="inputMethod"
                          value="youtube"
                          checked={inputMethod === 'youtube'}
                          onChange={(e) => setInputMethod(e.target.value as 'youtube' | 'upload')}
                          className="text-primary"
                        />
                        <span className="text-sm font-medium">YouTube URL</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="radio"
                          name="inputMethod"
                          value="upload"
                          checked={inputMethod === 'upload'}
                          onChange={(e) => setInputMethod(e.target.value as 'youtube' | 'upload')}
                          className="text-primary"
                        />
                        <span className="text-sm font-medium">Upload File</span>
                      </label>
                    </div>
                  </div>

                  {/* YouTube URL Input */}
                  {inputMethod === 'youtube' && (
                    <div className="space-y-2">
                      <Label htmlFor="youtubeUrl">YouTube URL</Label>
                      <Input
                        id="youtubeUrl"
                        name="youtubeUrl"
                        type="url"
                        placeholder="https://youtube.com/watch?v=..."
                        required={inputMethod === 'youtube'}
                        className="transition-all duration-200"
                      />
                      <p className="text-xs text-muted-foreground">
                        Enter a YouTube video URL to create compilations from
                      </p>
                    </div>
                  )}

                  {/* File Upload Input */}
                  {inputMethod === 'upload' && (
                    <div className="space-y-2">
                      <Label htmlFor="videoFile">Upload Video</Label>
                      <div className="space-y-3">
                        <input
                          id="videoFile"
                          type="file"
                          accept="video/*"
                          onChange={handleFileUpload}
                          disabled={isUploading}
                          className="block w-full text-sm text-muted-foreground
                            file:mr-4 file:py-2 file:px-4
                            file:rounded-md file:border-0
                            file:text-sm file:font-medium
                            file:bg-primary file:text-primary-foreground
                            hover:file:bg-primary/90 file:cursor-pointer
                            disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                        {isUploading && (
                          <p className="text-xs text-blue-600">Uploading...</p>
                        )}
                        {uploadedFile && !isUploading && (
                          <p className="text-xs text-green-600">
                            ✓ {uploadedFile.name} uploaded successfully
                          </p>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Upload a video file (MP4, AVI, MOV, MKV, etc.) to create compilations from
                      </p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="numCompilations">
                        Compilations
                        <FaQuestionCircle className="inline size-3 ml-1 opacity-60" />
                      </Label>
                      <Input
                        id="numCompilations"
                        name="numCompilations"
                        type="number"
                        min="1"
                        max="100"
                        defaultValue="1"
                        disabled={isUnlimited}
                        className="transition-all duration-200"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="maxReuse">
                        Max Reuse
                        <FaQuestionCircle className="inline size-3 ml-1 opacity-60" />
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

                  {/* Unlimited Generation Checkbox */}
                  <div className="space-y-2">
                    <Label htmlFor="unlimited">
                      Unlimited Generation
                      <FaQuestionCircle className="inline size-3 ml-1 opacity-60" />
                    </Label>
                      <div className="flex items-center space-x-2">
                        <input
                          id="unlimited"
                          name="unlimited"
                          type="checkbox"
                          checked={isUnlimited}
                          onChange={(e) => setIsUnlimited(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <Label htmlFor="unlimited" className="text-sm text-muted-foreground">
                          Generate unlimited compilations until clips are exhausted (limited by max reuse setting)
                        </Label>
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

                  {/* No-Background Variation Controls */}
                  <div className="space-y-4 p-4 rounded-lg border bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20">
                    <h3 className="text-sm font-semibold flex items-center gap-2">
                      <FaVideo className="size-4 text-purple-600" />
                      No-Background Variation Settings
                    </h3>
                    
                    {/* Generate No-Background Toggle */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div>
                          <Label htmlFor="generateNoBackground" className="font-medium">
                            Generate No-Background Version
                          </Label>
                          <p className="text-xs text-muted-foreground">
                            Creates a third variation without white background - pure video or blurred pillarbox
                          </p>
                        </div>
                      </div>
                      <Switch
                        id="generateNoBackground"
                        checked={generateNoBackground}
                        onCheckedChange={setGenerateNoBackground}
                      />
                    </div>

                    {/* Aspect Ratio Threshold Slider */}
                    {generateNoBackground && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="aspectRatioThreshold" className="font-medium">
                            9:16 Aspect Ratio Tolerance
                          </Label>
                          <span className="text-xs font-mono bg-muted px-2 py-1 rounded">
                            {blurredPillarboxThreshold[0].toFixed(2)}
                          </span>
                        </div>
                        <input
                          type="range"
                          id="aspectRatioThreshold"
                          min={0.05}
                          max={0.5}
                          step={0.01}
                          value={blurredPillarboxThreshold[0]}
                          onChange={(e) => setBlurredPillarboxThreshold([parseFloat(e.target.value)])}
                          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                        />
                        <p className="text-xs text-muted-foreground">
                          Lower values = stricter 9:16 requirement (more blurred backgrounds), 
                          Higher values = more tolerance (fewer blurred backgrounds)
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Local GPU Toggle */}
                  <div className="flex items-center justify-between p-4 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-3">
                      {useGpu ? (
                        <FaMicrochip className="size-5 text-green-500" />
                      ) : (
                        <FaMicrochip className="size-5 text-gray-500" />
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
                        <FaSpinner className="size-4 mr-2 animate-spin" />
                        Starting Compilation...
                      </>
                    ) : (
                      <>
                        <FaBrain className="size-4 mr-2" />
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
                    <FaQuestionCircle className="size-4 text-white" />
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
                      <p className="font-medium text-foreground">Generate Variations</p>
                      <p>Create up to 3 different versions: normal, TTS intro, and no-background</p>
                    </div>
                  </div>
                </div>
                
                <div className="mt-6 space-y-3">
                  <div className="p-3 rounded-lg bg-gradient-to-r from-blue-50 to-green-50 dark:from-blue-900/20 dark:to-green-900/20 border">
                    <p className="text-xs font-medium text-foreground mb-1">🎬 Video Variations:</p>
                    <ul className="text-xs text-muted-foreground space-y-1">
                      <li>• <strong>Normal:</strong> Traditional layout with white background</li>
                      <li>• <strong>TTS Intro:</strong> AI-generated introduction speech</li>
                      <li>• <strong>No-Background:</strong> Pure video or blurred pillarbox effect</li>
                    </ul>
                  </div>
                  
                  <div className="p-3 rounded-lg bg-muted/50 border">
                    <p className="text-xs text-muted-foreground">
                      <strong>Tip:</strong> Use longer source videos (10+ minutes) for better compilation variety
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}

