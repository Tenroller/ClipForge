'use client';

import { useState, useEffect } from 'react';
import { useGenerateBrainrotVideo, useJobs } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { FaSpinner, FaBrain, FaQuestionCircle, FaMicrochip, FaVideo } from 'react-icons/fa';
import type { JobRecord } from '@/lib/api';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export default function CompilationsPage() {
  const { toast } = useToast();
  const generateVideo = useGenerateBrainrotVideo();
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });

  const [busy, setBusy] = useState(false);
  const [useGpu, setUseGpu] = useState(true);
  const [isUnlimited, setIsUnlimited] = useState(false);
  const [generateNoBackground, setGenerateNoBackground] = useState(true);
  const [blurredPillarboxThreshold, setBlurredPillarboxThreshold] = useState(0.1);

  // Video input method selection
  const [inputMethod, setInputMethod] = useState<'youtube' | 'upload'>('youtube');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null);
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<JobRecord | null>(null);

  // Find the current job in the recent jobs list
  const currentJob = currentJobId
    ? recentJobs.find(job => job.id === currentJobId)
    : null;

  // Monitor job completion
  useEffect(() => {
    if (currentJob) {
      if (currentJob.status === 'completed') {
        setCompletedJob(currentJob);
        setCurrentJobId(null);
      } else if (currentJob.status === 'error' || currentJob.status === 'cancelled') {
        toast({
          title: 'Job Failed',
          description: currentJob.error_message || `Job ${currentJob.status}`,
          variant: 'destructive',
        });
        setCurrentJobId(null);
      }
    }
  }, [currentJob, toast]);

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
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setUploadedFileId(data.file_id);
      setUploadedFilePath(data.file_path);
      toast({
        title: 'Video uploaded successfully',
      });
    } catch (error: any) {
      toast({
        title: 'Upload failed',
        description: error.message,
        variant: 'destructive',
      });
      setUploadedFile(null);
      setUploadedFileId(null);
      setUploadedFilePath(null);
    } finally {
      setIsUploading(false);
    }
  };

  async function startBrainrot(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);

    const payload = {
      youtubeUrl: inputMethod === 'youtube' ? String(form.get('youtubeUrl') || '') : undefined,
      uploadedVideoPath: inputMethod === 'upload' ? uploadedFilePath : undefined,
      numCompilations: Number(form.get('numCompilations') || 1),
      minDuration: Number(form.get('minDuration') || 60),
      maxDuration: Number(form.get('maxDuration') || 110),
      maxReuse: Number(form.get('maxReuse') || 3),
      unlimited: isUnlimited,
      generateNoBackground: generateNoBackground,
      blurredPillarboxThreshold: blurredPillarboxThreshold,
    };

    // Validate that either YouTube URL or uploaded file is provided
    if (inputMethod === 'youtube' && !payload.youtubeUrl) {
      toast({
        title: 'YouTube URL is required',
        variant: 'destructive',
      });
      return;
    }

    if (inputMethod === 'upload' && !uploadedFilePath) {
      toast({
        title: 'Please upload a video file first',
        variant: 'destructive',
      });
      return;
    }

    setBusy(true);
    try {
      const data = await generateVideo.mutateAsync(payload);
      setCurrentJobId(data.jobId);
      setCompletedJob(null);

      toast({
        title: 'Starting the generation',
        description: `Job ID: ${data.jobId.substring(0, 8)}...`,
      });
    } catch (e: any) {
      toast({
        title: 'Generation failed',
        description: e.message,
        variant: 'destructive',
      });
    } finally {
      setBusy(false);
    }
  }

  const handleCloseResult = () => {
    setCompletedJob(null);
  };

  return (
    <div className="container-page">
      <div className="glass-header">
        <div>
          <h1 className="section-title">Video Compilation Generator</h1>
          <p className="section-subtitle">
            Create engaging compilation videos from YouTube content
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {/* Show job notification while generating */}
        {currentJobId && !completedJob && (
          <JobStartedNotification
            jobId={currentJobId}
            workflow="brainrot"
            autoRedirect={false}
          />
        )}

        {/* Show result panel when job completes */}
        {completedJob && (
          <ResultPanel
            job={completedJob}
            onClose={handleCloseResult}
          />
        )}

        {/* Show form when no active job or result */}
        {!currentJobId && !completedJob && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                            {blurredPillarboxThreshold.toFixed(2)}
                          </span>
                        </div>
                        <input
                          type="range"
                          id="aspectRatioThreshold"
                          min={0.05}
                          max={0.5}
                          step={0.01}
                          value={blurredPillarboxThreshold}
                          onChange={(e) => setBlurredPillarboxThreshold(parseFloat(e.target.value))}
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
  );
}
