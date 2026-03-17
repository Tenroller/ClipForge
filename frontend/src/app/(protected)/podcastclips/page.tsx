'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useJobs } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { useToast } from '@/hooks/use-toast';
import type { JobRecord, YouTubeMetadata } from '@/lib/api';
import { generatePodcastClips, getYouTubeMetadata, getThumbnailUrl, API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  Eye,
  Play,
  Sparkles,
  User,
  Video as VideoIcon,
  Zap,
  Settings2,
  Wand2,
  Youtube,
  Upload,
  Layers,
  LayoutDashboard,
  ArrowDownToLine,
  AlignCenter,
  ArrowUpToLine,
  Type,
  Palette
} from "lucide-react";
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from '@/lib/utils';

export default function PodcastClipsPage() {
  const { toast } = useToast();
  const t = useTranslations('podcastClips');
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });

  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<JobRecord | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form state
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [minDuration, setMinDuration] = useState(30);
  const [maxDuration, setMaxDuration] = useState(60);
  const [subtitleFontSize, setSubtitleFontSize] = useState(40);

  // Video input method selection
  const [inputMethod, setInputMethod] = useState<'youtube' | 'upload'>('youtube');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  // Advanced subtitle settings
  const [subtitleVerticalOffset, setSubtitleVerticalOffset] = useState(500);
  const [subtitleHighlightColor, setSubtitleHighlightColor] = useState('#FFD700');
  const [subtitleMaxWordsVisible, setSubtitleMaxWordsVisible] = useState(5);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Subtitle style options
  const [subtitleStyle, setSubtitleStyle] = useState('yellow_highlight');
  const [subtitleDisplayMode, setSubtitleDisplayMode] = useState('word');
  const [subtitlePosition, setSubtitlePosition] = useState('bottom');
  const [subtitleTextColor, setSubtitleTextColor] = useState('#FFFFFF');

  // YouTube metadata preview
  const [videoMetadata, setVideoMetadata] = useState<YouTubeMetadata | null>(null);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);

  // Constants moved inside component to support i18n
  const SUBTITLE_STYLES = [
    {
      id: 'yellow_highlight',
      name: t('subtitleStyles.yellowHighlight.name'),
      description: t('subtitleStyles.yellowHighlight.description'),
      previewClass: 'yellow-highlight'
    },
    {
      id: 'multicolor_pop',
      name: t('subtitleStyles.multicolorPop.name'),
      description: t('subtitleStyles.multicolorPop.description'),
      previewClass: 'multicolor'
    },
    {
      id: 'clean_outline',
      name: t('subtitleStyles.cleanOutline.name'),
      description: t('subtitleStyles.cleanOutline.description'),
      previewClass: 'outline'
    }
  ];

  const DISPLAY_MODES = [
    { id: 'word', name: t('displayModes.word'), icon: Type },
    { id: 'sentence', name: t('displayModes.sentence'), icon: LayoutDashboard } // Using LayoutDashboard as a proxy for 'block' of text
  ];

  const SUBTITLE_POSITIONS = [
    { id: 'top', name: t('positions.top'), icon: ArrowUpToLine },
    { id: 'center', name: t('positions.center'), icon: AlignCenter },
    { id: 'bottom', name: t('positions.bottom'), icon: ArrowDownToLine }
  ];

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
        const clipsCount = (currentJob.result && typeof currentJob.result === 'object' && 'clips_count' in currentJob.result)
          ? (currentJob.result as { clips_count?: unknown }).clips_count
          : 'multiple';
        toast({
          title: t('clipsGenerated'),
          description: t('successfullyCreated', { count: String(clipsCount) }),
        });
      } else if (currentJob.status === 'error' || currentJob.status === 'cancelled') {
        toast({
          title: t('jobFailed'),
          description: currentJob.error_message || `Job ${currentJob.status}`,
          variant: 'destructive',
        });
        setCurrentJobId(null);
      }
    }
  }, [currentJob, toast, t]);

  // Fetch YouTube metadata when URL changes
  useEffect(() => {
    const fetchMetadata = async () => {
      const urlTrimmed = youtubeUrl.trim();

      if (!urlTrimmed || !urlTrimmed.includes('youtube.com') && !urlTrimmed.includes('youtu.be')) {
        setVideoMetadata(null);
        return;
      }

      setIsLoadingMetadata(true);
      try {
        const metadata = await getYouTubeMetadata(urlTrimmed);
        setVideoMetadata(metadata);
      } catch (error: unknown) {
        console.error('Failed to fetch YouTube metadata:', error);
        setVideoMetadata(null);
      } finally {
        setIsLoadingMetadata(false);
      }
    };

    const timeoutId = setTimeout(fetchMetadata, 800);
    return () => clearTimeout(timeoutId);
  }, [youtubeUrl]);

  // Helper: get CSRF token
  const getCsrfToken = async (): Promise<string | undefined> => {
    let csrfToken = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1];
    if (csrfToken) return decodeURIComponent(csrfToken);
    try {
      const res = await fetch(`${API_BASE}/api/auth/csrf-token`, { credentials: 'include' });
      if (res.ok) return (await res.json()).csrf_token;
    } catch { /* best-effort */ }
    return undefined;
  };

  const CHUNK_SIZE = 80 * 1024 * 1024; // 80MB

  // File upload function
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadedFile(file);
    setUploadProgress(0);

    try {
      const csrfToken = await getCsrfToken();
      const headers: Record<string, string> = {};
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

      let data: { file_id: string; file_path: string; [key: string]: unknown };

      if (file.size <= CHUNK_SIZE) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/api/upload-video`, {
          method: 'POST',
          body: formData,
          credentials: 'include',
          headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => null);
          throw new Error(errBody?.detail || `Upload failed: ${response.statusText}`);
        }

        setUploadProgress(100);
        data = await response.json();
      } else {
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

        const initRes = await fetch(`${API_BASE}/api/upload-video/init`, {
          method: 'POST',
          credentials: 'include',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, total_size: file.size }),
        });
        if (!initRes.ok) {
          const errBody = await initRes.json().catch(() => null);
          throw new Error(errBody?.detail || `Init failed: ${initRes.statusText}`);
        }
        const { upload_id } = await initRes.json();

        for (let i = 0; i < totalChunks; i++) {
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const blob = file.slice(start, end);

          let success = false;
          for (let attempt = 0; attempt < 3; attempt++) {
            try {
              const chunkForm = new FormData();
              chunkForm.append('upload_id', upload_id);
              chunkForm.append('chunk_index', String(i));
              chunkForm.append('chunk', blob, file.name);

              const chunkRes = await fetch(`${API_BASE}/api/upload-video/chunk`, {
                method: 'POST',
                body: chunkForm,
                credentials: 'include',
                headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
              });

              if (!chunkRes.ok) {
                const errBody = await chunkRes.json().catch(() => null);
                throw new Error(errBody?.detail || `Chunk ${i} failed: ${chunkRes.statusText}`);
              }

              success = true;
              break;
            } catch (err) {
              if (attempt === 2) throw err;
              await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
            }
          }

          if (!success) throw new Error(`Failed to upload chunk ${i} after 3 attempts`);
          setUploadProgress(Math.round(((i + 1) / totalChunks) * 95));
        }

        const finalRes = await fetch(`${API_BASE}/api/upload-video/finalize`, {
          method: 'POST',
          credentials: 'include',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ upload_id }),
        });
        if (!finalRes.ok) {
          const errBody = await finalRes.json().catch(() => null);
          throw new Error(errBody?.detail || `Finalize failed: ${finalRes.statusText}`);
        }

        setUploadProgress(100);
        data = await finalRes.json();
      }

      setUploadedFilePath(data.file_path);
      toast({ title: t('videoUploaded') });
    } catch (error: unknown) {
      toast({
        title: t('uploadFailed'),
        description: (error as Error).message,
        variant: 'destructive',
      });
      setUploadedFile(null);
      setUploadedFilePath(null);
      setUploadProgress(0);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (inputMethod === 'youtube' && !youtubeUrl.trim()) {
      toast({
        title: t('youtubeUrlRequired'),
        description: t('enterValidUrl'),
        variant: 'destructive',
      });
      return;
    }

    if (inputMethod === 'upload' && !uploadedFilePath) {
      toast({
        title: t('uploadVideoFirst'),
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        youtubeUrl: inputMethod === 'youtube' ? youtubeUrl.trim() : undefined,
        uploadedVideoPath: inputMethod === 'upload' ? uploadedFilePath : undefined,
        minDuration,
        maxDuration,
        useGPU: false, // User requested CPU only
        subtitleFontSize,
        subtitleColor: subtitleTextColor,
        subtitleStrokeColor: '#000000',
        subtitleStrokeWidth: 2,
        subtitleVerticalOffset,
        subtitleHighlightColor,
        subtitleMaxWordsVisible,
        subtitleStyle,
        subtitleDisplayMode,
        subtitlePosition,
      };

      const data = await generatePodcastClips(payload);
      setCurrentJobId(data.jobId);

      toast({
        title: t('jobStarted'),
        description: t('generatingClipsAuto'),
      });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to start podcast clips generation';
      toast({
        title: t('error'),
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const viewCountLabel = videoMetadata?.view_count != null
    ? `${(videoMetadata.view_count / 1000000).toFixed(1)}M`
    : '—';

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Header - matches compilations/creator style */}
      <div className="mb-8 space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <Zap className="h-8 w-8 text-muted-foreground" />
          {t('title')}
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl">
          {t('description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form */}
        <div className="lg:col-span-8 space-y-6">
          {/* Job notification */}
          {currentJob && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <JobStartedNotification
                jobId={currentJob.id}
                status={currentJob.status}
                progress={currentJob.progress}
                currentStep={currentJob.current_step}
              />
            </div>
          )}

          {/* Result panel */}
          {completedJob && (
            <ResultPanel
              job={completedJob}
              onClose={() => setCompletedJob(null)}
            />
          )}

          {!currentJobId && !completedJob && (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Video Source Card */}
              <Card className="overflow-hidden">
                <CardHeader className="pb-6 border-b">
                  <div className="flex items-center gap-2">
                    <Layers className="w-5 h-5 text-muted-foreground" />
                    <CardTitle className="text-lg font-medium">{t('videoSource')}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  <Tabs defaultValue="youtube" value={inputMethod} onValueChange={(v) => setInputMethod(v as 'youtube' | 'upload')}>
                    <TabsList className="grid w-full grid-cols-2 mb-6">
                      <TabsTrigger value="youtube" className="flex items-center gap-2">
                        <Youtube className="w-4 h-4" />
                        {t('youtubeUrl')}
                      </TabsTrigger>
                      <TabsTrigger value="upload" className="flex items-center gap-2">
                        <Upload className="w-4 h-4" />
                        {t('uploadFile')}
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="youtube" className="space-y-4">
                      <div className="space-y-2">
                        <div className="relative">
                          <Youtube className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            id="youtubeUrl"
                            placeholder="https://youtube.com/watch?v=..."
                            value={youtubeUrl}
                            onChange={(e) => setYoutubeUrl(e.target.value)}
                            disabled={isSubmitting || !!currentJobId}
                            className="pl-9"
                          />
                        </div>
                      </div>

                      {/* Video Metadata Preview */}
                      {videoMetadata && (
                        <div className="animate-in fade-in slide-in-from-top-4 duration-500">
                          <div className="rounded-lg border bg-muted/30 overflow-hidden flex flex-col md:flex-row">
                            <div className="relative md:w-48 aspect-video md:aspect-auto bg-muted group overflow-hidden shrink-0">
                              {videoMetadata.thumbnail_url ? (
                                <Image
                                  src={getThumbnailUrl(videoMetadata.thumbnail_url)}
                                  alt={videoMetadata.title}
                                  fill
                                  className="object-cover"
                                />
                              ) : (
                                <div className="flex items-center justify-center h-full w-full bg-muted">
                                  <VideoIcon className="h-8 w-8 text-muted-foreground" />
                                </div>
                              )}
                              <div className="absolute inset-0 bg-black/10 group-hover:bg-black/20 flex items-center justify-center transition-colors">
                                <Play className="w-8 h-8 text-white opacity-80" />
                              </div>
                            </div>
                            <div className="p-4 flex flex-col justify-center gap-2">
                              <h3 className="font-semibold text-sm line-clamp-1">{videoMetadata.title}</h3>
                              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                <div className="flex items-center gap-1.5">
                                  <User className="w-3 h-3" /> {videoMetadata.channel}
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <Clock className="w-3 h-3" /> {videoMetadata.duration_formatted}
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <Eye className="w-3 h-3" /> {viewCountLabel}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="upload" className="space-y-4">
                      <div className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:bg-muted/20 transition-colors">
                        <Input
                          id="videoFile"
                          type="file"
                          accept="video/*"
                          onChange={handleFileUpload}
                          disabled={isUploading}
                          className="hidden"
                        />
                        <Label htmlFor="videoFile" className="cursor-pointer block space-y-4">
                          <div className="mx-auto bg-muted rounded-full w-12 h-12 flex items-center justify-center">
                            <Upload className="w-6 h-6 text-muted-foreground" />
                          </div>
                          <div>
                            {uploadedFile ? (
                              <div className="flex items-center justify-center gap-2 text-green-600 font-medium">
                                <span className="bg-green-100 dark:bg-green-900/30 p-1 rounded-full"><VideoIcon className="w-3 h-3" /></span>
                                {uploadedFile.name}
                              </div>
                            ) : (
                              <span className="font-medium">{t('uploadVideo')}</span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {isUploading ? (
                              <div className="space-y-2 w-full max-w-xs mx-auto">
                                <div className="flex justify-between text-xs">
                                  <span>{t('uploading')}</span>
                                  <span className="font-mono">{uploadProgress}%</span>
                                </div>
                                <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
                                    style={{ width: `${uploadProgress}%` }}
                                  />
                                </div>
                              </div>
                            ) : t('uploadVideoDescription')}
                          </div>
                        </Label>
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>

              {/* Configuration Card */}
              <Card className="overflow-hidden">
                <CardHeader className="pb-6 border-b">
                  <div className="flex items-center gap-2">
                    <Settings2 className="w-5 h-5 text-muted-foreground" />
                    <CardTitle className="text-lg font-medium">{t('clipSettings')}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="p-6 space-y-8">
                  {/* Duration Settings */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Clock className="w-4 h-4" />
                      Duration
                    </div>
                    <div className="space-y-6">
                      <div className="space-y-3">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-muted-foreground">{t('minDuration')}</span>
                          <Badge variant="outline" className="font-mono bg-background">{minDuration}s</Badge>
                        </div>
                        <Slider
                          min={15} max={60} step={5}
                          value={[minDuration]}
                          onValueChange={(v) => setMinDuration(v[0])}
                          className="py-1"
                        />
                      </div>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-muted-foreground">{t('maxDuration')}</span>
                          <Badge variant="outline" className="font-mono bg-background">{maxDuration}s</Badge>
                        </div>
                        <Slider
                          min={30} max={120} step={5}
                          value={[maxDuration]}
                          onValueChange={(v) => setMaxDuration(v[0])}
                          className="py-1"
                        />
                      </div>
                    </div>
                  </div>

                  <Separator />

                  {/* Subtitle Style */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Wand2 className="w-4 h-4" />
                      {t('subtitleStyle')}
                    </div>
                    <div className="space-y-3">
                      {SUBTITLE_STYLES.map((style) => (
                        <div
                          key={style.id}
                          className={cn(
                            "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all hover:border-primary/50",
                            subtitleStyle === style.id ? "bg-primary/5 border-primary shadow-sm" : "bg-muted/30 border-transparent"
                          )}
                          onClick={() => setSubtitleStyle(style.id)}
                        >
                          <span className="text-sm font-medium pl-2">{style.name}</span>
                          <div className="w-20 h-6 bg-black/80 rounded flex items-center justify-center overflow-hidden">
                            <div className={cn(
                              "text-[8px] font-bold whitespace-nowrap px-1",
                              style.id === 'yellow_highlight' || style.id === 'multicolor_pop' ? "text-white" : "text-white italic"
                            )}>
                              {style.id === 'yellow_highlight' && <span className="bg-yellow-400 text-black px-0.5 rounded-[1px]">ABC</span>}
                              {style.id === 'multicolor_pop' && <span className="text-pink-400">ABC</span>}
                              {style.id === 'clean_outline' && "ABC"}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* Appearance */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Palette className="w-4 h-4" />
                      {t('appearance')}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">{t('displayMode')}</Label>
                        <div className="flex gap-1">
                          {DISPLAY_MODES.map((mode) => (
                            <div
                              key={mode.id}
                              className={cn(
                                "flex-1 h-9 flex items-center justify-center rounded border cursor-pointer transition-colors",
                                subtitleDisplayMode === mode.id ? "bg-primary/10 border-primary text-primary" : "bg-muted/30 border-transparent hover:bg-muted"
                              )}
                              onClick={() => setSubtitleDisplayMode(mode.id)}
                              title={mode.name}
                            >
                              <mode.icon className="w-4 h-4" />
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">{t('positionLabel')}</Label>
                        <div className="flex gap-1">
                          {SUBTITLE_POSITIONS.map((pos) => (
                            <div
                              key={pos.id}
                              className={cn(
                                "flex-1 h-9 flex items-center justify-center rounded border cursor-pointer transition-colors",
                                subtitlePosition === pos.id ? "bg-primary/10 border-primary text-primary" : "bg-muted/30 border-transparent hover:bg-muted"
                              )}
                              onClick={() => setSubtitlePosition(pos.id)}
                              title={pos.name}
                            >
                              <pos.icon className="w-4 h-4" />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    size="lg"
                    disabled={isSubmitting || !!currentJobId || (inputMethod === 'youtube' ? !youtubeUrl : !uploadedFilePath)}
                    className="w-full"
                  >
                    <span className="flex items-center justify-center gap-2">
                      {isSubmitting ? (
                        <>
                          <div className="h-5 w-5 animate-spin rounded-full border-2 border-background border-t-transparent" />
                          {t('starting')}...
                        </>
                      ) : (
                        <>
                          <Zap className="w-5 h-5 fill-current" />
                          {t('generateViralClipsButton')}
                        </>
                      )}
                    </span>
                  </Button>
                </CardContent>
              </Card>
            </form>
          )}
        </div>

        {/* Right Column: Info & Help */}
        <div className="lg:col-span-4 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-muted-foreground" />
                <CardTitle className="text-base">{t('aiDetection')}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="relative pl-4 space-y-6 border-l-2 border-border">
                {[
                  { title: t('aiDetection'), desc: t('viralMoments') },
                  { title: t('faceTracking'), desc: t('smartCropping') },
                ].map((step, i) => (
                  <div key={i} className="relative">
                    <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-muted-foreground border-2 border-background" />
                    <h4 className="font-medium text-sm">{step.title}</h4>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{step.desc}</p>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-lg bg-muted border text-xs">
                <span className="font-semibold block mb-1">{t('clipSettings')}</span>
                <span className="text-muted-foreground">
                  {t('description')}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
