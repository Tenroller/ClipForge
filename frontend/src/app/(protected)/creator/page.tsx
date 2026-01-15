'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useGenerateMoneyPrinterVideo, useJobs, useAvailableModels, useAvailableVoices } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import MoneyPrinterForm from '@/components/moneyprinter/MoneyPrinterForm';
import PreviewPanel from '@/components/moneyprinter/PreviewPanel';
import { useToast } from '@/hooks/use-toast';
import type { JobRecord } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

type Position =
  | "left-top"
  | "center-top"
  | "right-top"
  | "left-middle"
  | "center-middle"
  | "right-middle"
  | "left-bottom"
  | "center-bottom"
  | "right-bottom";

export default function CreatorPage() {
  const { toast } = useToast();
  const t = useTranslations('creator');
  const generateVideo = useGenerateMoneyPrinterVideo();
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });
  const { data: models = [] } = useAvailableModels();
  const { data: voices = [] } = useAvailableVoices();

  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<JobRecord | null>(null);

  // Form state
  const [aiModel, setAiModel] = useState('gemini-2.0-flash');
  const [voice, setVoice] = useState('af_bella');
  const [subtitleColor, setSubtitleColor] = useState('#FFFF00');
  const [subtitlesPosition, setSubtitlesPosition] = useState('center,bottom');
  const [position, setPosition] = useState<Position>('center-bottom');
  const [positionRaw, setPositionRaw] = useState<string>('');

  // Shadow layer state for preview
  const [shadowLayersCount, setShadowLayersCount] = useState(4);
  const [shadowLayer1Color, setShadowLayer1Color] = useState('#4A90E2');
  const [shadowLayer2Color, setShadowLayer2Color] = useState('#357ABD');
  const [shadowLayer3Color, setShadowLayer3Color] = useState('#2E5F8A');
  const [shadowLayer4Color, setShadowLayer4Color] = useState('#1E3F5A');

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
          title: t('jobFailed'),
          description: currentJob.error_message || `Job ${currentJob.status}`,
          variant: 'destructive',
        });
        setCurrentJobId(null);
      }
    }
  }, [currentJob, toast, t]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const form = new FormData(e.currentTarget);

    // Extract all form data (hidden inputs included)
    const videoSubject = String(form.get('videoSubject') || '');
    if (!videoSubject.trim()) {
      toast({
        title: t('subjectRequired'),
        description: t('enterVideoSubject'),
        variant: 'destructive',
      });
      return;
    }

    // Build the payload with all form fields
    const payload: any = {
      video_subject: videoSubject,
      ai_model: String(form.get('aiModel') || aiModel),
      voice: String(form.get('voice') || voice),
      paragraph_number: Number(form.get('paragraphNumber') || 1),
      threads: Number(form.get('threads') || 2),
      subtitles_position: String(form.get('subtitlesPosition') || subtitlesPosition),
      color: String(form.get('color') || subtitleColor),
      use_music: form.get('useMusic') === '1',
      use_gpu: form.get('useGPU') === '1',
      custom_prompt: String(form.get('customPrompt') || '') || null,
      zip_url: String(form.get('zipUrl') || '') || null,

      // TikTok subtitle settings
      use_tiktok_subtitles: form.get('useTikTokSubtitles') === 'true',
      subtitle_font: String(form.get('subtitleFont') || 'Arial'),
      subtitle_font_size: Number(form.get('subtitleFontSize') || 48),
      subtitle_default_color: String(form.get('subtitleDefaultColor') || '#FFFFFF'),
      subtitle_highlight_color: String(form.get('subtitleHighlightColor') || '#FFFFFF'),
      subtitle_stroke_color: String(form.get('subtitleStrokeColor') || '#000000'),
      subtitle_background_color: String(form.get('subtitleBackgroundColor') || '#000000'),
      subtitle_stroke_width: Number(form.get('subtitleStrokeWidth') || 0),
      subtitle_background_opacity: Number(form.get('subtitleBackgroundOpacity') || 0.0),
      subtitle_padding_x: Number(form.get('subtitlePaddingX') || 20),
      subtitle_padding_y: Number(form.get('subtitlePaddingY') || 16),

      // Shadow layers
      shadow_layers_count: Number(form.get('shadowLayersCount') || 4),
      shadow_layer1_color: String(form.get('shadowLayer1Color') || '#4A90E2'),
      shadow_layer2_color: String(form.get('shadowLayer2Color') || '#357ABD'),
      shadow_layer3_color: String(form.get('shadowLayer3Color') || '#2E5F8A'),
      shadow_layer4_color: String(form.get('shadowLayer4Color') || '#1E3F5A'),

      // Whisper enhanced
      use_whisper_enhanced: form.get('useWhisperEnhanced') === 'true',
      whisper_model: String(form.get('whisperModel') || 'base'),
    };

    try {
      const result = await generateVideo.mutateAsync(payload);
      setCurrentJobId(result.jobId);
      setCompletedJob(null);

      toast({
        title: t('videoGenerationStarted'),
        description: `Job ID: ${result.jobId.substring(0, 8)}...`,
      });
    } catch (error: any) {
      toast({
        title: t('generationFailed'),
        description: error.message || t('failedToStartGeneration'),
        variant: 'destructive',
      });
    }
  };

  const handleReset = () => {
    setAiModel('gemini-2.0-flash');
    setVoice('af_bella');
    setSubtitleColor('#FFFF00');
    setSubtitlesPosition('center,bottom');
    setPosition('center-bottom');
    setPositionRaw('');
    setShadowLayersCount(4);
    setShadowLayer1Color('#4A90E2');
    setShadowLayer2Color('#357ABD');
    setShadowLayer3Color('#2E5F8A');
    setShadowLayer4Color('#1E3F5A');
  };

  const handlePositionChange = (pos: Position) => {
    setPosition(pos);
    // Convert position format: "center-bottom" -> "center,bottom"
    const gridFormat = pos.replace('-', ',');
    setSubtitlesPosition(gridFormat);
    setPositionRaw(''); // Clear custom position when using grid
  };

  const handlePositionRawChange = (raw: string) => {
    setPositionRaw(raw);
    setSubtitlesPosition(raw); // Pass raw position to backend
  };

  const handleCloseResult = () => {
    setCompletedJob(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('description')}
        </p>
      </div>

      <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[2fr,1fr]">
        <div className="space-y-6">
          {/* Show job notification while generating */}
          {currentJobId && !completedJob && (
            <JobStartedNotification
              jobId={currentJobId}
              workflow="moneyprinter"
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
            <MoneyPrinterForm
              models={models}
              aiModel={aiModel}
              onChangeAiModel={setAiModel}
              voices={voices}
              voice={voice}
              onChangeVoice={setVoice}
              subtitleColor={subtitleColor}
              onChangeSubtitleColor={setSubtitleColor}
              subtitlesPosition={subtitlesPosition}
              apiBase={API_BASE}
              busy={generateVideo.isPending}
              onSubmit={handleSubmit}
              onReset={handleReset}
              formId="moneyprinter-form"
              // Shadow layer control for real-time preview sync
              shadowLayersCount={shadowLayersCount}
              onChangeShadowLayersCount={setShadowLayersCount}
              shadowLayer1Color={shadowLayer1Color}
              onChangeShadowLayer1Color={setShadowLayer1Color}
              shadowLayer2Color={shadowLayer2Color}
              onChangeShadowLayer2Color={setShadowLayer2Color}
              shadowLayer3Color={shadowLayer3Color}
              onChangeShadowLayer3Color={setShadowLayer3Color}
              shadowLayer4Color={shadowLayer4Color}
              onChangeShadowLayer4Color={setShadowLayer4Color}
            />
          )}
        </div>

        {/* Preview & Recent Jobs Column */}
        <div className="space-y-6">
          {/* Preview Panel - Only show when form is visible */}
          {!currentJobId && !completedJob && (
            <PreviewPanel
              position={position}
              onChangePosition={handlePositionChange}
              color={subtitleColor}
              positionRaw={positionRaw}
              onChangePositionRaw={handlePositionRawChange}
              shadowLayersCount={shadowLayersCount}
              shadowLayer1Color={shadowLayer1Color}
              shadowLayer2Color={shadowLayer2Color}
              shadowLayer3Color={shadowLayer3Color}
              shadowLayer4Color={shadowLayer4Color}
            />
          )}

          {/* Recent Jobs Card */}
          <div className="border rounded-xl bg-card/50 backdrop-blur-sm p-5 shadow-md hover:shadow-lg transition-all duration-300">
            <h3 className="text-base font-bold mb-4 flex items-center gap-2">
              <div className="size-2 rounded-full bg-primary animate-pulse" />
              {t('recentJobs')}
            </h3>
            <div className="space-y-2">
              {recentJobs.length === 0 ? (
                <div className="text-center py-8">
                  <div className="size-12 rounded-full bg-muted mx-auto mb-3 flex items-center justify-center">
                    <svg className="size-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                  </div>
                  <p className="text-sm text-muted-foreground">{t('noRecentJobs')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('startCreating')}</p>
                </div>
              ) : (
                recentJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="p-3 rounded-lg border bg-card hover:bg-accent/50 hover:border-primary/30 transition-all duration-200 cursor-pointer hover:-translate-y-0.5 hover:shadow-md group"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <code className="text-xs font-mono text-muted-foreground group-hover:text-foreground transition-colors">
                        {job.id.substring(0, 8)}...
                      </code>
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium transition-all ${job.status === 'completed'
                        ? 'bg-success/10 text-success border border-success/20'
                        : job.status === 'error' || job.status === 'cancelled'
                          ? 'bg-destructive/10 text-destructive border border-destructive/20'
                          : 'bg-info/10 text-info border border-info/20 animate-pulse'
                        }`}>
                        {job.status}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate mb-1">
                      {job.workflow === 'moneyprinter' ? t('aiVideo') : t('compilation')}
                    </p>
                    {job.current_step && (
                      <p className="text-xs text-muted-foreground mt-1.5 truncate">
                        <span className="font-medium">{t('step')}:</span> {job.current_step}
                      </p>
                    )}
                    {job.progress !== undefined && job.progress >= 0 && (
                      <div className="mt-2">
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-300 rounded-full"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
