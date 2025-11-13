'use client';

import { useState, useEffect, useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { useJobs, useAvailableModels } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { useToast } from '@/hooks/use-toast';
import type { JobRecord, YouTubeMetadata } from '@/lib/api';
import { generatePodcastClips, getYouTubeMetadata, getThumbnailUrl } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import Image from 'next/image';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { ChevronDown, ChevronUp, Clock, Eye, Play, Sparkles, Target, User, Video as VideoIcon, Zap } from "lucide-react";

export default function PodcastClipsPage() {
  const { toast } = useToast();
  const t = useTranslations('podcastClips');
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });
  const { data: allModels = [] } = useAvailableModels();

  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<JobRecord | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form state
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [aiModel, setAiModel] = useState('gemini-2.5-flash');
  const [whisperModel, setWhisperModel] = useState('base');
  const [maxClipCount, setMaxClipCount] = useState(15);
  const [minDuration, setMinDuration] = useState(30);
  const [maxDuration, setMaxDuration] = useState(60);
  const [subtitleFontSize, setSubtitleFontSize] = useState(40);

  // Advanced subtitle settings (karaoke-style)
  const [subtitleVerticalOffset, setSubtitleVerticalOffset] = useState(500);
  const [subtitleHighlightColor, setSubtitleHighlightColor] = useState('#6366f1');
  const [subtitleMaxWordsVisible, setSubtitleMaxWordsVisible] = useState(5);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // YouTube metadata preview
  const [videoMetadata, setVideoMetadata] = useState<YouTubeMetadata | null>(null);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);

  // Viral keywords
  const [viralKeywords, setViralKeywords] = useState('');

  // Mixed-mode content detection
  const [enableMixedMode, setEnableMixedMode] = useState(true);
  const [useOCR, setUseOCR] = useState(true);
  const [faceLossThreshold, setFaceLossThreshold] = useState(1.0);
  const [faceReturnThreshold, setFaceReturnThreshold] = useState(0.5);
  const [minSegmentDuration, setMinSegmentDuration] = useState(0.5);
  const [transitionDuration, setTransitionDuration] = useState(0.5);
  const [showMixedModeSettings, setShowMixedModeSettings] = useState(false);

  // Organize models into categories for better UX (mutually exclusive)
  const organizedModels = useMemo(() => {
    if (!allModels.length) {
      return {
        recommended: ['gemini-2.0-flash', 'gemini-2.5-flash'],
        stable: [],
        experimental: [],
      };
    }

    // First, identify experimental models (has precedence)
    const experimental = allModels.filter(m =>
      m.includes('exp') || m.includes('preview') || m.includes('thinking')
    );

    // Then, identify recommended models that are NOT experimental
    const recommended = allModels.filter(m =>
      !experimental.includes(m) &&
      (m.includes('2.5-flash') || m.includes('2.0-flash') ||
       m.includes('2.5-pro') || m.includes('2.0-pro'))
    );

    // Finally, stable models that are neither recommended nor experimental
    const stable = allModels.filter(m =>
      !recommended.includes(m) &&
      !experimental.includes(m) &&
      (m.includes('gemini') || m.includes('gemma'))
    );

    return { recommended, stable, experimental };
  }, [allModels]);

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

      // Check if it's a valid YouTube URL pattern
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
        // Don't show error toast yet, only when they try to submit
      } finally {
        setIsLoadingMetadata(false);
      }
    };

    // Debounce the metadata fetch
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
      // Parse viral keywords from comma-separated string
      const keywordsArray = viralKeywords
        .split(',')
        .map(k => k.trim())
        .filter(k => k.length > 0);

      const payload = {
        youtubeUrl: youtubeUrl.trim(),
        aiModel,
        whisperModel,
        maxClipCount,
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
        viralFocusKeywords: keywordsArray,
        // Mixed-mode content detection settings
        enableMixedMode,
        useOCR,
        faceLossThreshold,
        faceReturnThreshold,
        minSegmentDuration,
        transitionDuration,
      };

      const data = await generatePodcastClips(payload);
      setCurrentJobId(data.jobId);

      toast({
        title: t('jobStarted'),
        description: t('generatingClips', { max: maxClipCount }),
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
      {/* Header */}
      <div className="mb-8 space-y-2">
        <div className="inline-block">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
            {t('title')}
          </h1>
          <div className="h-1 w-24 bg-gradient-to-r from-primary to-accent rounded-full mt-2" />
        </div>
        <p className="text-base text-muted-foreground max-w-2xl">
          {t('description')}
        </p>
      </div>

      {/* Features Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-purple-500" />
              <div>
                <p className="font-semibold text-sm">{t('aiDetection')}</p>
                <p className="text-xs text-muted-foreground">{t('viralMoments')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Target className="h-5 w-5 text-blue-500" />
              <div>
                <p className="font-semibold text-sm">{t('faceTracking')}</p>
                <p className="text-xs text-muted-foreground">{t('smartCropping')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Zap className="h-5 w-5 text-yellow-500" />
              <div>
                <p className="font-semibold text-sm">{t('parallelGen')}</p>
                <p className="text-xs text-muted-foreground">{t('fasterProcessing')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <VideoIcon className="h-5 w-5 text-green-500" />
              <div>
                <p className="font-semibold text-sm">{t('socialFormat')}</p>
                <p className="text-xs text-muted-foreground">{t('socialReady')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Generation Form */}
        <div className="lg:col-span-2">
          <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
            <CardHeader className="pb-4">
              <CardTitle>{t('generateViralClips')}</CardTitle>
              <CardDescription>
                {t('enterYoutubePodcast')}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* YouTube URL */}
                <div className="space-y-2">
                  <Label htmlFor="youtubeUrl">{t('youtubePodcastUrl')}</Label>
                  <Input
                    id="youtubeUrl"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                {/* YouTube Video Preview */}
                {isLoadingMetadata && (
                  <Card className="rounded-xl border-blue-200 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-800/30 shadow-sm backdrop-blur-sm">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent" />
                        <p className="text-sm text-muted-foreground">{t('loadingVideoDetails')}</p>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {videoMetadata && !isLoadingMetadata && (
                  <Card className="rounded-xl border-green-200 bg-green-50/50 dark:bg-green-950/20 dark:border-green-800/30 shadow-sm backdrop-blur-sm">
                    <CardContent className="p-4">
                      <div className="flex gap-4">
                        {/* Thumbnail */}
                        <div className="relative flex-shrink-0 w-32 h-20 rounded-lg overflow-hidden bg-muted">
                          {videoMetadata.thumbnail_url ? (
                            <Image
                              src={getThumbnailUrl(videoMetadata.thumbnail_url)}
                              alt={videoMetadata.title}
                              width={128}
                              height={80}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <VideoIcon className="h-8 w-8 text-muted-foreground" />
                            </div>
                          )}
                          <div className="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/10 transition-colors">
                            <Play className="h-8 w-8 text-white drop-shadow-lg" />
                          </div>
                        </div>

                        {/* Video Info */}
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-sm line-clamp-2 mb-2">{videoMetadata.title}</h3>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              <span className="truncate max-w-[150px]">{videoMetadata.channel}</span>
                            </div>
                            {videoMetadata.duration && (
                              <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                <span>{videoMetadata.duration_formatted}</span>
                              </div>
                            )}
                            {videoMetadata.view_count && (
                              <div className="flex items-center gap-1">
                                <Eye className="h-3 w-3" />
                                <span>{(videoMetadata.view_count / 1000000).toFixed(1)}M views</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* AI Model */}
                <div className="space-y-2">
                  <Label htmlFor="aiModel">{t('aiModelViralDetection')}</Label>
                  <Select value={aiModel} onValueChange={setAiModel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="max-h-[400px]">
                      {/* Recommended Models */}
                      {organizedModels.recommended.length > 0 && (
                        <>
                          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                            {t('recommended')}
                          </div>
                          {organizedModels.recommended.slice(0, 6).map((model) => (
                            <SelectItem key={model} value={model}>
                              {model}
                              {model === 'gemini-2.5-flash' && ` ${t('fastest')}`}
                              {model === 'gemini-2.0-flash' && ` ${t('default')}`}
                            </SelectItem>
                          ))}
                        </>
                      )}

                      {/* Stable Models */}
                      {organizedModels.stable.length > 0 && (
                        <>
                          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t mt-1 pt-2">
                            {t('otherModels')}
                          </div>
                          {organizedModels.stable.map((model) => (
                            <SelectItem key={model} value={model}>
                              {model}
                            </SelectItem>
                          ))}
                        </>
                      )}

                      {/* Experimental Models */}
                      {organizedModels.experimental.length > 0 && (
                        <>
                          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t mt-1 pt-2">
                            {t('experimental')}
                          </div>
                          {organizedModels.experimental.slice(0, 5).map((model) => (
                            <SelectItem key={model} value={model}>
                              {model} 🧪
                            </SelectItem>
                          ))}
                        </>
                      )}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {allModels.length > 0 ? t('modelsAvailable', { count: allModels.length }) : t('loadingModels')}
                  </p>
                </div>

                {/* Whisper Model */}
                <div className="space-y-2">
                  <Label htmlFor="whisperModel">{t('transcriptionModel')}</Label>
                  <Select value={whisperModel} onValueChange={setWhisperModel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem key="tiny" value="tiny">{t('tiny')}</SelectItem>
                      <SelectItem key="base" value="base">{t('base')}</SelectItem>
                      <SelectItem key="small" value="small">{t('small')}</SelectItem>
                      <SelectItem key="medium" value="medium">{t('medium')}</SelectItem>
                      <SelectItem key="turbo" value="turbo">{t('turbo')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Max Clip Count */}
                <div className="space-y-2">
                  <Label htmlFor="maxClipCount">
                    {t('maximumClips')} <Badge variant="secondary">{maxClipCount}</Badge>
                  </Label>
                  <Slider
                    id="maxClipCount"
                    min={3}
                    max={30}
                    step={1}
                    value={[maxClipCount]}
                    onValueChange={(value) => setMaxClipCount(value[0])}
                    disabled={isSubmitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('aiWillGenerate', { max: maxClipCount })}
                  </p>
                </div>

                {/* Duration Range */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="minDuration">
                      {t('minDuration')} <Badge variant="outline">{minDuration}s</Badge>
                    </Label>
                    <Slider
                      id="minDuration"
                      min={15}
                      max={60}
                      step={5}
                      value={[minDuration]}
                      onValueChange={(value) => setMinDuration(value[0])}
                      disabled={isSubmitting}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="maxDuration">
                      {t('maxDuration')} <Badge variant="outline">{maxDuration}s</Badge>
                    </Label>
                    <Slider
                      id="maxDuration"
                      min={30}
                      max={120}
                      step={5}
                      value={[maxDuration]}
                      onValueChange={(value) => setMaxDuration(value[0])}
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                {/* Subtitle Font Size */}
                <div className="space-y-2">
                  <Label htmlFor="subtitleFontSize">
                    {t('subtitleFontSize')} <Badge variant="secondary">{subtitleFontSize}px</Badge>
                  </Label>
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

                {/* Viral Keywords */}
                <div className="space-y-2">
                  <Label htmlFor="viralKeywords">
                    {t('viralFocusKeywords')} <Badge variant="outline" className="ml-2">{t('optional')}</Badge>
                  </Label>
                  <Input
                    id="viralKeywords"
                    placeholder={t('keywordsPlaceholder')}
                    value={viralKeywords}
                    onChange={(e) => setViralKeywords(e.target.value)}
                    disabled={isSubmitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('keywordsDescription')}
                  </p>
                </div>

                {/* Mixed-Mode Content Detection */}
                <div className="border rounded-lg p-4 space-y-4 bg-muted/30">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Label htmlFor="enableMixedMode">{t('smartContentDetection')}</Label>
                        <Badge variant="secondary">{t('aiPowered')}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t('autoSwitchModes')}
                      </p>
                    </div>
                    <Switch
                      id="enableMixedMode"
                      checked={enableMixedMode}
                      onCheckedChange={setEnableMixedMode}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label htmlFor="useOCR">{t('ocrTextDetection')}</Label>
                      <p className="text-xs text-muted-foreground">
                        {t('detectTextContent')}
                      </p>
                    </div>
                    <Switch
                      id="useOCR"
                      checked={useOCR}
                      onCheckedChange={setUseOCR}
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* Advanced Mixed-Mode Settings */}
                  {enableMixedMode && (
                    <div className="pt-2 border-t">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="w-full flex items-center justify-between hover:bg-muted/50"
                        onClick={() => setShowMixedModeSettings(!showMixedModeSettings)}
                      >
                        <span className="text-sm">{t('advancedDetectionSettings')}</span>
                        {showMixedModeSettings ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>

                      {showMixedModeSettings && (
                        <div className="mt-4 space-y-4">
                          {/* Face Loss Threshold */}
                          <div className="space-y-2">
                            <Label htmlFor="faceLossThreshold">
                              {t('faceLossThreshold')} <Badge variant="secondary">{faceLossThreshold}s</Badge>
                            </Label>
                            <Slider
                              id="faceLossThreshold"
                              min={0.5}
                              max={3.0}
                              step={0.1}
                              value={[faceLossThreshold]}
                              onValueChange={(value) => setFaceLossThreshold(value[0])}
                              disabled={isSubmitting}
                            />
                            <p className="text-xs text-muted-foreground">
                              {t('faceLossDescription')}
                            </p>
                          </div>

                          {/* Face Return Threshold */}
                          <div className="space-y-2">
                            <Label htmlFor="faceReturnThreshold">
                              Face Return Threshold: <Badge variant="secondary">{faceReturnThreshold}s</Badge>
                            </Label>
                            <Slider
                              id="faceReturnThreshold"
                              min={0.2}
                              max={2.0}
                              step={0.1}
                              value={[faceReturnThreshold]}
                              onValueChange={(value) => setFaceReturnThreshold(value[0])}
                              disabled={isSubmitting}
                            />
                            <p className="text-xs text-muted-foreground">
                              Seconds with face to return to face-focused mode
                            </p>
                          </div>

                          {/* Min Segment Duration */}
                          <div className="space-y-2">
                            <Label htmlFor="minSegmentDuration">
                              Min Segment Duration: <Badge variant="secondary">{minSegmentDuration}s</Badge>
                            </Label>
                            <Slider
                              id="minSegmentDuration"
                              min={0.3}
                              max={2.0}
                              step={0.1}
                              value={[minSegmentDuration]}
                              onValueChange={(value) => setMinSegmentDuration(value[0])}
                              disabled={isSubmitting}
                            />
                            <p className="text-xs text-muted-foreground">
                              Minimum duration to avoid flickering between modes
                            </p>
                          </div>

                          {/* Transition Duration */}
                          <div className="space-y-2">
                            <Label htmlFor="transitionDuration">
                              Transition Duration: <Badge variant="secondary">{transitionDuration}s</Badge>
                            </Label>
                            <Slider
                              id="transitionDuration"
                              min={0.2}
                              max={1.0}
                              step={0.1}
                              value={[transitionDuration]}
                              onValueChange={(value) => setTransitionDuration(value[0])}
                              disabled={isSubmitting}
                            />
                            <p className="text-xs text-muted-foreground">
                              Crossfade duration when switching between modes
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Advanced Subtitle Settings (Collapsible) */}
                <div className="border rounded-lg bg-muted/30">
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full flex items-center justify-between p-4 hover:bg-muted/50 rounded-lg"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                  >
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      <span className="font-semibold">{t('advancedSubtitleSettings')}</span>
                      <Badge variant="outline" className="ml-2">{t('karaokeStyle')}</Badge>
                    </div>
                    {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </Button>

                  {showAdvanced && (
                    <div className="p-4 pt-0 space-y-4 border-t bg-muted/30">
                      <p className="text-sm text-muted-foreground mb-4">
                        {t('customizeKaraoke')}
                      </p>

                      {/* Vertical Offset */}
                      <div className="space-y-2">
                        <Label htmlFor="subtitleVerticalOffset">
                          Vertical Position: <Badge variant="secondary">{subtitleVerticalOffset}px from bottom</Badge>
                        </Label>
                        <Slider
                          id="subtitleVerticalOffset"
                          min={100}
                          max={1000}
                          step={50}
                          value={[subtitleVerticalOffset]}
                          onValueChange={(value) => setSubtitleVerticalOffset(value[0])}
                          disabled={isSubmitting}
                        />
                        <p className="text-xs text-muted-foreground">
                          Higher values move subtitles toward center (recommended: 400-600)
                        </p>
                      </div>

                      {/* Highlight Color */}
                      <div className="space-y-2">
                        <Label htmlFor="subtitleHighlightColor">
                          Highlight Box Color
                        </Label>
                        <div className="flex items-center gap-3">
                          <Input
                            id="subtitleHighlightColor"
                            type="color"
                            value={subtitleHighlightColor}
                            onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                            disabled={isSubmitting}
                            className="w-20 h-10 cursor-pointer"
                          />
                          <Input
                            type="text"
                            value={subtitleHighlightColor}
                            onChange={(e) => setSubtitleHighlightColor(e.target.value)}
                            disabled={isSubmitting}
                            placeholder="#6366f1"
                            className="flex-1 font-mono"
                          />
                          <div
                            className="w-10 h-10 rounded border-2 border-border"
                            style={{ backgroundColor: subtitleHighlightColor }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Background color for the currently spoken word
                        </p>
                      </div>

                      {/* Max Words Visible */}
                      <div className="space-y-2">
                        <Label htmlFor="subtitleMaxWordsVisible">
                          Words in View: <Badge variant="secondary">{subtitleMaxWordsVisible} words</Badge>
                        </Label>
                        <Slider
                          id="subtitleMaxWordsVisible"
                          min={1}
                          max={10}
                          step={1}
                          value={[subtitleMaxWordsVisible]}
                          onValueChange={(value) => setSubtitleMaxWordsVisible(value[0])}
                          disabled={isSubmitting}
                        />
                        <p className="text-xs text-muted-foreground">
                          Number of words shown at once (current word + context)
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={isSubmitting || !!currentJobId}
                >
                  {isSubmitting ? t('starting') : currentJobId ? t('processing') : t('generateViralClipsButton')}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Status Panel */}
        <div className="space-y-6">
          {/* Current Job */}
          {currentJob && (
            <JobStartedNotification
              jobId={currentJob.id}
              status={currentJob.status}
              progress={currentJob.progress}
              currentStep={currentJob.current_step}
            />
          )}

          {/* Completed Job */}
          {completedJob && (
            <ResultPanel
              job={completedJob}
              onClose={() => setCompletedJob(null)}
            />
          )}

          {/* Info Card */}
          {!currentJob && !completedJob && (
            <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">{t('howItWorks')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm pt-0">
                <div className="space-y-2">
                  <p className="font-semibold">{t('aiAnalysis')}</p>
                  <p className="text-muted-foreground">
                    {t('aiAnalysisDesc')}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">{t('smartCroppingStep')}</p>
                  <p className="text-muted-foreground">
                    {t('smartCroppingDesc')}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">{t('hookOptimization')}</p>
                  <p className="text-muted-foreground">
                    {t('hookOptimizationDesc')}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">{t('audioEnhancement')}</p>
                  <p className="text-muted-foreground">
                    {t('audioEnhancementDesc')}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">{t('thumbnails')}</p>
                  <p className="text-muted-foreground">
                    {t('thumbnailsDesc')}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
