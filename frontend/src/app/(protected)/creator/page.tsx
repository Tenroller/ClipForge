'use client';

import { useState, useEffect } from 'react';
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
          title: 'Job Failed',
          description: currentJob.error_message || `Job ${currentJob.status}`,
          variant: 'destructive',
        });
        setCurrentJobId(null);
      }
    }
  }, [currentJob, toast]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const form = new FormData(e.currentTarget);

    // Extract all form data (hidden inputs included)
    const videoSubject = String(form.get('videoSubject') || '');
    if (!videoSubject.trim()) {
      toast({
        title: 'Subject Required',
        description: 'Please enter a video subject',
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
        title: 'Video Generation Started',
        description: `Job ID: ${result.jobId.substring(0, 8)}...`,
      });
    } catch (error: any) {
      toast({
        title: 'Generation Failed',
        description: error.message || 'Failed to start video generation',
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
    <div className="container-page">
      <div className="glass-header">
        <div>
          <h1 className="section-title">AI Video Creator</h1>
          <p className="section-subtitle">
            Generate videos with AI-powered scripts and stock footage
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
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
          <div className="enhanced-card p-4">
            <h3 className="text-sm font-semibold mb-3">Recent Jobs</h3>
            <div className="space-y-2">
              {recentJobs.length === 0 ? (
                <p className="text-xs text-muted-foreground">No recent jobs</p>
              ) : (
                recentJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <code className="text-xs font-mono">
                        {job.id.substring(0, 8)}...
                      </code>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        job.status === 'completed'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : job.status === 'error' || job.status === 'cancelled'
                          ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                          : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
                      }`}>
                        {job.status}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {job.workflow === 'moneyprinter' ? 'AI Video' : 'Compilation'}
                    </p>
                    {job.current_step && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Step: {job.current_step}
                      </p>
                    )}
                    {job.progress !== undefined && job.progress >= 0 && (
                      <div className="mt-2">
                        <div className="h-1 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all duration-300"
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
