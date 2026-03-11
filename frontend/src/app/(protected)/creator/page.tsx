'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { useGenerateMoneyPrinterVideo, useJobs, useAvailableVoices } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import MoneyPrinterForm from '@/components/moneyprinter/MoneyPrinterForm';
import PreviewPanel from '@/components/moneyprinter/PreviewPanel';
import PresetManager from '@/components/presets/PresetManager';
import { useToast } from '@/hooks/use-toast';
import { usePresets } from '@/hooks/usePresets';
import type { PresetConfig } from '@/hooks/usePresets';
import type { JobRecord } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Sparkles, Wand2 } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

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

  // Presets
  const { presets, savePreset, loadPreset, deletePreset, renamePreset } = usePresets();

  const getCurrentConfig = useCallback((): PresetConfig => ({
    aiModel,
    voice,
    subtitleColor,
    subtitlesPosition,
    position,
    positionRaw,
    shadowLayersCount,
    shadowLayer1Color,
    shadowLayer2Color,
    shadowLayer3Color,
    shadowLayer4Color,
  }), [aiModel, voice, subtitleColor, subtitlesPosition, position, positionRaw, shadowLayersCount, shadowLayer1Color, shadowLayer2Color, shadowLayer3Color, shadowLayer4Color]);

  const handleLoadPreset = useCallback((config: PresetConfig) => {
    setAiModel(config.aiModel);
    setVoice(config.voice);
    setSubtitleColor(config.subtitleColor);
    setSubtitlesPosition(config.subtitlesPosition);
    setPosition(config.position as Position);
    setPositionRaw(config.positionRaw);
    setShadowLayersCount(config.shadowLayersCount);
    setShadowLayer1Color(config.shadowLayer1Color);
    setShadowLayer2Color(config.shadowLayer2Color);
    setShadowLayer3Color(config.shadowLayer3Color);
    setShadowLayer4Color(config.shadowLayer4Color);
  }, []);

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
      use_gpu: false,
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
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      {/* Header */}
      <div className="mb-8 space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <Wand2 className="h-8 w-8 text-muted-foreground" />
          {t('title')}
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl">
          {t('description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form Configuration */}
        <div className="lg:col-span-8 space-y-6">
          {!currentJobId && !completedJob && (
            <Card className="overflow-hidden">
              <CardHeader className="pb-6 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-muted-foreground" />
                    <CardTitle className="text-lg font-medium">{t('videoConfiguration')}</CardTitle>
                  </div>
                  <PresetManager
                    presets={presets}
                    onSave={savePreset}
                    onLoad={handleLoadPreset}
                    onDelete={deletePreset}
                    onRename={renamePreset}
                    getCurrentConfig={getCurrentConfig}
                  />
                </div>
              </CardHeader>
              <CardContent className="p-6">
                <MoneyPrinterForm
                  aiModel={aiModel}
                  voices={voices}
                  voice={voice}
                  onChangeVoice={setVoice}
                  subtitleColor={subtitleColor}
                  onChangeSubtitleColor={setSubtitleColor}
                  subtitlesPosition={subtitlesPosition}
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
              </CardContent>
            </Card>
          )}

          {/* Show job notification while generating */}
          {currentJobId && !completedJob && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <JobStartedNotification
                jobId={currentJobId}
                workflow="moneyprinter"
                autoRedirect={false}
              />
            </div>
          )}

          {/* Show result panel when job completes */}
          {completedJob && (
            <ResultPanel
              job={completedJob}
              onClose={handleCloseResult}
            />
          )}
        </div>

        {/* Right Column: Preview & Recent Jobs */}
        <div className="lg:col-span-4 space-y-6">
          {/* Preview Panel - Only show when form is visible */}
          {!currentJobId && !completedJob && (
            <div className="sticky top-6 space-y-6">
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

              <Card>
                <CardHeader className="py-4">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                    </span>
                    {t('recentJobs')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-3">
                    {recentJobs.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground text-sm">
                        {t('noRecentJobs')}
                      </div>
                    ) : (
                      recentJobs.slice(0, 5).map((job) => (
                        <div
                          key={job.id}
                          className="group flex flex-col gap-2 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 border border-transparent hover:border-border/50 transition-all cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs text-muted-foreground">{job.id.substring(0, 8)}</span>
                            <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${job.status === 'completed'
                              ? 'bg-green-500/10 text-green-600'
                              : job.status === 'error' || job.status === 'cancelled'
                                ? 'bg-red-500/10 text-red-600'
                                : 'bg-blue-500/10 text-blue-600'
                              }`}>
                              {job.status}
                            </span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-muted-foreground">{t('aiVideo')}</span>
                            {job.progress !== undefined && job.progress > 0 && job.progress < 100 && (
                              <span className="font-medium">{job.progress}%</span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
