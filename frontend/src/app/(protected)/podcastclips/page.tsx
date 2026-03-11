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
  Youtube,
  LayoutDashboard,
  ArrowDownToLine,
  AlignCenter,
  ArrowUpToLine,
  Type,
  Palette
} from "lucide-react";
import { Separator } from '@/components/ui/separator';
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

      {/* Page Header */}
      <div className="text-center mb-10 space-y-4 pt-4">
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
          {t('title')}
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto leading-relaxed">
          {t('description')}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="relative space-y-8">

        {/* ROW 1: YouTube Search Bar */}
        <div className="relative z-10 w-full max-w-5xl mx-auto">
          <div className="relative group">
            <div className="relative bg-background rounded-lg border p-2 flex items-center gap-3">
              <div className="pl-3 text-muted-foreground">
                <Youtube className="w-6 h-6" />
              </div>
              <Input
                id="youtubeUrl"
                placeholder={t('youtubeUrlLabel')}
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                disabled={isSubmitting || !!currentJobId}
                className="border-0 shadow-none focus-visible:ring-0 text-lg py-6 px-2 placeholder:text-muted-foreground/50 h-14 bg-transparent"
              />
              {/* Optional: Add a 'Clear' or 'Paste' button here if needed */}
            </div>
          </div>
        </div>

        {/* ROW 2: Video Preview & Features (Moved here as requested) */}
        <div className="w-full max-w-5xl mx-auto">
          {/* Video Metadata Preview - Only show if URL is entered */}
          {videoMetadata && !currentJob && !completedJob && (
            <div className="w-full animate-in fade-in slide-in-from-top-4 duration-500 mb-6">
              <div className="rounded-xl border bg-card/50 overflow-hidden flex flex-col md:flex-row shadow-sm hover:shadow-md transition-all">
                <div className="relative md:w-64 aspect-video md:aspect-auto bg-muted group overflow-hidden shrink-0">
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
                    <Play className="w-10 h-10 text-white opacity-80" />
                  </div>
                </div>
                <div className="p-5 flex flex-col justify-center gap-2">
                  <h3 className="font-semibold text-lg line-clamp-1">{videoMetadata.title}</h3>
                  <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded">
                      <User className="w-3.5 h-3.5" /> {videoMetadata.channel}
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded">
                      <Clock className="w-3.5 h-3.5" /> {videoMetadata.duration_formatted}
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded">
                      <Eye className="w-3.5 h-3.5" /> {viewCountLabel}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Features / Placeholder if no URL */}
          {!videoMetadata && !currentJob && !completedJob && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full opacity-60 hover:opacity-100 transition-opacity mb-6">
              <FeatureCard
                icon={<Sparkles className="h-6 w-6 text-muted-foreground" />}
                title={t('aiDetection')}
                desc={t('viralMoments')}
              />
              <FeatureCard
                icon={<Target className="h-6 w-6 text-muted-foreground" />}
                title={t('faceTracking')}
                desc={t('smartCropping')}
              />
            </div>
          )}
        </div>

        {/* ROW 3: Horizontal Configuration Panel */}
        <Card className="overflow-hidden max-w-5xl mx-auto">
          <CardHeader className="px-6 py-4 border-b">
            <div className="flex items-center gap-2">
              <Settings2 className="w-5 h-5 text-primary" />
              <CardTitle className="text-base font-semibold">{t('clipSettings')}</CardTitle>
            </div>
          </CardHeader>

          <CardContent className="p-6">
            {/* 3-Column Horizontal Grid for Settings */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

              {/* Column 1: Duration (4 cols) */}
              <div className="md:col-span-4 space-y-6 border-r md:border-r-border/60 md:pr-6 border-transparent">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  <h4 className="font-medium text-sm text-foreground">Duration</h4>
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

              {/* Column 2: Styles (4 cols) */}
              <div className="md:col-span-4 space-y-6 border-r md:border-r-border/60 md:pr-6 border-transparent">
                <div className="flex items-center gap-2 mb-4">
                  <Wand2 className="w-4 h-4 text-muted-foreground" />
                  <h4 className="font-medium text-sm text-foreground">{t('subtitleStyle')}</h4>
                </div>

                <div className="space-y-3">
                  {SUBTITLE_STYLES.map((style) => (
                    <div
                      key={style.id}
                      className={cn(
                        "flex items-center justify-between p-2 rounded-lg border cursor-pointer transition-all hover:border-primary/50",
                        subtitleStyle === style.id ? "bg-primary/5 border-primary shadow-sm" : "bg-muted/30 border-transparent"
                      )}
                      onClick={() => setSubtitleStyle(style.id)}
                    >
                      <span className="text-sm font-medium pl-2">{style.name}</span>
                      {/* Mini Preview Dot/Box */}
                      <div className="w-20 h-6 bg-black/80 rounded flex items-center justify-center overflow-hidden">
                        <div className={cn(
                          "text-[8px] font-bold whitespace-nowrap px-1",
                          style.id === 'yellow_highlight' ? "text-white" :
                            style.id === 'multicolor_pop' ? "text-white" : "text-white italic"
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

              {/* Column 3: Appearance & Act (4 cols) */}
              <div className="md:col-span-4 space-y-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Palette className="w-4 h-4 text-muted-foreground" />
                    <h4 className="font-medium text-sm text-foreground">{t('appearance')}</h4>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="space-y-2">
                      <Label className="text-[10px] uppercase text-muted-foreground">{t('displayMode')}</Label>
                      <div className="flex gap-1">
                        {DISPLAY_MODES.map((mode) => (
                          <div
                            key={mode.id}
                            className={cn(
                              "flex-1 h-8 flex items-center justify-center rounded border cursor-pointer transition-colors",
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
                      <Label className="text-[10px] uppercase text-muted-foreground">{t('positionLabel')}</Label>
                      <div className="flex gap-1">
                        {SUBTITLE_POSITIONS.map((pos) => (
                          <div
                            key={pos.id}
                            className={cn(
                              "flex-1 h-8 flex items-center justify-center rounded border cursor-pointer transition-colors",
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

                {/* Main Action Button */}
                <Button
                  type="submit"
                  className="w-full font-bold text-base py-6"
                  size="lg"
                  disabled={isSubmitting || !!currentJobId || !youtubeUrl}
                >
                  {isSubmitting ? (
                    <>
                      <div className="h-5 w-5 mr-3 animate-spin rounded-full border-2 border-background border-t-transparent" />
                      {t('starting')}...
                    </>
                  ) : (
                    <>
                      <Zap className="w-5 h-5 mr-2 fill-current" />
                      {t('generateViralClipsButton')}
                    </>
                  )}
                </Button>
              </div>

            </div>
          </CardContent>
        </Card>

        {/* ROW 4: Results Section (At Bottom) */}
        <div className="space-y-6 pb-20 max-w-5xl mx-auto">
          {currentJob && (
            <div className="w-full">
              <JobStartedNotification
                jobId={currentJob.id}
                status={currentJob.status}
                progress={currentJob.progress}
                currentStep={currentJob.current_step}
              />
            </div>
          )}

          {completedJob && (
            <div className="animate-in fade-in slide-in-from-bottom-8 duration-700 w-full">
              <ResultPanel
                job={completedJob}
                onClose={() => setCompletedJob(null)}
              />
            </div>
          )}
        </div>

      </form>
    </div>
  );
}

// Sub-components for cleaner render
function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="flex items-center gap-4 p-4 rounded-lg border">
      <div className="p-3 rounded-lg bg-muted">
        {icon}
      </div>
      <div>
        <h4 className="font-semibold text-base mb-1">{title}</h4>
        <p className="text-sm text-muted-foreground leading-snug">{desc}</p>
      </div>
    </div>
  );
}
