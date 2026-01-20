'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useJobs } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { useToast } from '@/hooks/use-toast';
import type { JobRecord, YouTubeMetadata } from '@/lib/api';
import { generatePodcastClips, getYouTubeMetadata, getThumbnailUrl } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Image from 'next/image';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import {
  ChevronDown,
  ChevronUp,
  Clock,
  Eye,
  Play,
  Sparkles,
  Target,
  User,
  Video as VideoIcon,
  Zap,
  Settings2,
  Wand2,
  Youtube
} from "lucide-react";
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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

  // Advanced subtitle settings
  const [subtitleVerticalOffset, setSubtitleVerticalOffset] = useState(500);
  const [subtitleHighlightColor, setSubtitleHighlightColor] = useState('#6366f1');
  const [subtitleMaxWordsVisible, setSubtitleMaxWordsVisible] = useState(5);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // YouTube metadata preview
  const [videoMetadata, setVideoMetadata] = useState<YouTubeMetadata | null>(null);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);

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

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!youtubeUrl.trim()) {
      toast({
        title: t('youtubeUrlRequired'),
        description: t('enterValidUrl'),
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        youtubeUrl: youtubeUrl.trim(),
        minDuration,
        maxDuration,
        useGPU: true,
        subtitleFontSize,
        subtitleColor: '#FFFFFF',
        subtitleStrokeColor: '#000000',
        subtitleStrokeWidth: 2,
        subtitleVerticalOffset,
        subtitleHighlightColor,
        subtitleMaxWordsVisible,
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

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Page Header */}
      <div className="mb-8 space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">{t('title')}</h1>
        <p className="text-muted-foreground text-lg max-w-2xl">
          {t('description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Input & Results (8 cols) */}
        <div className="lg:col-span-8 space-y-6">

          {/* Main Input Card */}
          <Card className="border-border/50 shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/30 pb-6 border-b border-border/50">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg text-red-600 dark:text-red-400">
                  <Youtube className="w-5 h-5" />
                </div>
                <CardTitle className="text-lg font-medium">{t('sourceVideo')}</CardTitle>
              </div>
              <CardDescription className="text-base">
                Paste a YouTube URL to automatically detect speakers, transcribe audio, and generate viral clips.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-6 space-y-6">
              <div className="space-y-3">
                <Label htmlFor="youtubeUrl" className="text-sm font-medium ml-1">YouTube URL</Label>
                <div className="relative">
                  <Input
                    id="youtubeUrl"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    disabled={isSubmitting || !!currentJobId}
                    className="pl-10 h-12 text-base shadow-sm ring-offset-background placeholder:text-muted-foreground/50"
                  />
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <VideoIcon className="h-5 w-5" />
                  </div>
                </div>
              </div>

              {/* Video Preview State */}
              <div className="min-h-[140px] transition-all duration-300 ease-in-out">
                {isLoadingMetadata ? (
                  <div className="h-32 rounded-xl border border-dashed border-muted-foreground/25 bg-muted/20 flex flex-col items-center justify-center gap-3 animate-pulse">
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent" />
                    <p className="text-sm text-muted-foreground font-medium">{t('loadingVideoDetails')}</p>
                  </div>
                ) : videoMetadata ? (
                  <div className="rounded-xl border bg-card overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex flex-col sm:flex-row">
                      <div className="relative sm:w-48 aspect-video sm:aspect-auto bg-muted group">
                        {videoMetadata.thumbnail_url ? (
                          <Image
                            src={getThumbnailUrl(videoMetadata.thumbnail_url)}
                            alt={videoMetadata.title}
                            fill
                            className="object-cover transition-transform duration-500 group-hover:scale-105"
                          />
                        ) : (
                          <div className="flex items-center justify-center h-full w-full">
                            <VideoIcon className="h-8 w-8 text-muted-foreground" />
                          </div>
                        )}
                        <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                          <div className="bg-background/90 rounded-full p-2 shadow-lg backdrop-blur-sm">
                            <Play className="h-5 w-5 text-primary fill-primary" />
                          </div>
                        </div>
                      </div>
                      <div className="p-4 flex-1 flex flex-col justify-center gap-2">
                        <h3 className="font-semibold text-base line-clamp-2 leading-tight">
                          {videoMetadata.title}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded-md">
                            <User className="h-3.5 w-3.5" />
                            <span className="truncate max-w-[150px] font-medium">{videoMetadata.channel}</span>
                          </div>
                          {videoMetadata.duration && (
                            <div className="flex items-center gap-1.5">
                              <Clock className="h-3.5 w-3.5" />
                              <span>{videoMetadata.duration_formatted}</span>
                            </div>
                          )}
                          {videoMetadata.view_count && (
                            <div className="flex items-center gap-1.5">
                              <Eye className="h-3.5 w-3.5" />
                              <span>{(videoMetadata.view_count / 1000000).toFixed(1)}M views</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-32 rounded-xl border border-dashed border-muted-foreground/20 bg-muted/5 flex flex-col items-center justify-center gap-2">
                    <div className="p-2 rounded-full bg-muted/30">
                      <SearchIllustration className="h-6 w-6 text-muted-foreground/40" />
                    </div>
                    <p className="text-sm text-muted-foreground/60">Video details will appear here</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Results Area */}
          <div className="space-y-6">
            {currentJob && (
              <JobStartedNotification
                jobId={currentJob.id}
                status={currentJob.status}
                progress={currentJob.progress}
                currentStep={currentJob.current_step}
              />
            )}

            {completedJob && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <ResultPanel
                  job={completedJob}
                  onClose={() => setCompletedJob(null)}
                />
              </div>
            )}

            {/* Features Info (When idle) */}
            {!currentJob && !completedJob && (
              <div className="grid grid-cols-2 gap-4">
                <FeatureCard
                  icon={<Sparkles className="h-5 w-5 text-purple-500" />}
                  title={t('aiDetection')}
                  desc={t('viralMoments')}
                />
                <FeatureCard
                  icon={<Target className="h-5 w-5 text-blue-500" />}
                  title={t('faceTracking')}
                  desc={t('smartCropping')}
                />
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Configuration (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">

            <Card className="border-border/50 shadow-sm h-fit">
              <CardHeader className="bg-muted/30 pb-4 border-b border-border/50">
                <div className="flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-primary" />
                  <CardTitle className="text-base font-medium">Clip Settings</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="p-6 space-y-8">

                {/* Duration Controls */}
                <div className="space-y-5">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">{t('minDuration')}</Label>
                      <Badge variant="secondary" className="font-mono">{minDuration}s</Badge>
                    </div>
                    <Slider
                      min={15}
                      max={60}
                      step={5}
                      value={[minDuration]}
                      onValueChange={(value) => setMinDuration(value[0])}
                      disabled={isSubmitting}
                      className="py-1"
                    />
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">{t('maxDuration')}</Label>
                      <Badge variant="secondary" className="font-mono">{maxDuration}s</Badge>
                    </div>
                    <Slider
                      min={30}
                      max={120}
                      step={5}
                      value={[maxDuration]}
                      onValueChange={(value) => setMaxDuration(value[0])}
                      disabled={isSubmitting}
                      className="py-1"
                    />
                  </div>
                </div>

                <Separator />

                {/* Appearance */}
                <div className="space-y-5">
                  <div className="flex items-center gap-2 mb-2">
                    <Wand2 className="w-4 h-4 text-muted-foreground" />
                    <h4 className="text-sm font-medium text-muted-foreground">Appearance</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="subtitleFontSize" className="text-sm font-medium">{t('subtitleFontSize')}</Label>
                      <span className="text-xs text-muted-foreground font-mono">{subtitleFontSize}px</span>
                    </div>
                    <Slider
                      id="subtitleFontSize"
                      min={20}
                      max={80}
                      step={5}
                      value={[subtitleFontSize]}
                      onValueChange={(value) => setSubtitleFontSize(value[0])}
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* Advanced Toggle */}
                  <div className="pt-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full justify-between"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                    >
                      <span className="text-xs">{t('advancedSubtitleSettings')}</span>
                      {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    </Button>

                    {showAdvanced && (
                      <div className="mt-4 space-y-5 animate-in slide-in-from-top-2 duration-200">
                        <div className="space-y-2">
                          <Label className="text-xs">Vertical Position</Label>
                          <Slider
                            min={100}
                            max={1000}
                            step={50}
                            value={[subtitleVerticalOffset]}
                            onValueChange={(v) => setSubtitleVerticalOffset(v[0])}
                            disabled={isSubmitting}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label className="text-xs">Highlight Color</Label>
                          <div className="flex items-center gap-2">
                            <div className="relative overflow-hidden rounded-md border w-8 h-8 shrink-0">
                              <Input
                                type="color"
                                value={subtitleHighlightColor}
                                onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                                className="absolute inset-0 p-0 h-[150%] w-[150%] -top-[25%] -left-[25%] cursor-pointer border-0"
                                disabled={isSubmitting}
                              />
                            </div>
                            <Input
                              value={subtitleHighlightColor}
                              onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                              className="h-8 font-mono text-xs uppercase"
                              maxLength={7}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
              <CardFooter className="bg-muted/10 p-4 border-t border-border/50">
                <Button
                  type="submit"
                  className="w-full font-semibold shadow-lg shadow-primary/20 transition-all hover:shadow-primary/30"
                  size="lg"
                  disabled={isSubmitting || !!currentJobId || !youtubeUrl}
                >
                  {isSubmitting ? (
                    <>
                      <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-background border-t-transparent" />
                      {t('starting')}
                    </>
                  ) : currentJobId ? (
                    <>
                      {t('processing')}
                      <span className="ml-1 opacity-70">...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4 mr-2 fill-current" />
                      {t('generateViralClipsButton')}
                    </>
                  )}
                </Button>
              </CardFooter>
            </Card>

            {/* Helper Tips */}
            <div className="bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30 rounded-lg p-4 text-sm text-blue-900 dark:text-blue-200">
              <div className="flex items-start gap-3">
                <div className="p-1 bg-blue-100 dark:bg-blue-900/40 rounded-full mt-0.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                </div>
                <div className="space-y-1">
                  <p className="font-semibold text-xs uppercase tracking-wide opacity-80">Pro Tip</p>
                  <p className="opacity-90 leading-relaxed text-xs">
                    Videos between <strong>15-30 minutes</strong> yield the best results. The AI looks for engaging dialogue hooks.
                  </p>
                </div>
              </div>
            </div>

          </form>
        </div>
      </div>
    </div>
  );
}

// Sub-components for cleaner render
function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="flex items-center gap-3 p-4 rounded-xl border bg-card hover:bg-muted/50 transition-colors">
      <div className="p-2 bg-muted rounded-lg">
        {icon}
      </div>
      <div>
        <p className="font-medium text-sm leading-none mb-1.5">{title}</p>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
    </div>
  );
}

function SearchIllustration({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  )
}
