'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useGenerateBrainrotVideo, useJobs } from '@/hooks/use-jobs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { Brain, Cpu, HelpCircle, Loader2, Video as VideoIcon, Youtube, Upload, Layers, Settings2, Clock, Smartphone } from "lucide-react";
import type { JobRecord } from '@/lib/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export default function CompilationsPage() {
  const { toast } = useToast();
  const t = useTranslations('compilations');
  const generateVideo = useGenerateBrainrotVideo();
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });

  const [busy, setBusy] = useState(false);
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
          title: t('jobFailed'),
          description: currentJob.error_message || `Job ${currentJob.status}`,
          variant: 'destructive',
        });
        setCurrentJobId(null);
      }
    }
  }, [currentJob, toast, t]);

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
        title: t('videoUploaded'),
      });
    } catch (error: unknown) {
      toast({
        title: t('uploadFailed'),
        description: (error as Error).message,
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
        title: t('youtubeUrlRequired'),
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

    setBusy(true);
    try {
      const data = await generateVideo.mutateAsync(payload);
      setCurrentJobId(data.jobId);
      setCompletedJob(null);

      toast({
        title: t('startingGeneration'),
        description: `Job ID: ${data.jobId.substring(0, 8)}...`,
      });
    } catch (e: unknown) {
      toast({
        title: t('generationFailed'),
        description: (e as Error).message,
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
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-500">
      <div className="mb-8 space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <Brain className="h-8 w-8 text-primary" />
          {t('title')}
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl">
          {t('description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form Configuration */}
        <div className="lg:col-span-8 space-y-6">
          {/* Show job notification while generating */}
          {currentJobId && !completedJob && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <JobStartedNotification
                jobId={currentJobId}
                workflow="brainrot"
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

          {!currentJobId && !completedJob && (
            <form onSubmit={startBrainrot} className="space-y-6">
              {/* Source Selection Card */}
              <Card className="border-border/50 shadow-sm overflow-hidden bg-card/50 backdrop-blur-sm">
                <CardHeader className="bg-muted/30 pb-6 border-b border-border/50">
                  <div className="flex items-center gap-2">
                    <div className="p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg text-white">
                      <Layers className="w-5 h-5" />
                    </div>
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
                        <Label htmlFor="youtubeUrl">{t('youtubeUrl')}</Label>
                        <div className="relative">
                          <Youtube className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            id="youtubeUrl"
                            name="youtubeUrl"
                            type="url"
                            placeholder="https://youtube.com/watch?v=..."
                            className="pl-9"
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">{t('enterYoutubeUrl')}</p>
                      </div>
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
                            {isUploading ? t('uploading') : t('uploadVideoDescription')}
                          </div>
                        </Label>
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>

              {/* Configuration Card */}
              <Card className="border-border/50 shadow-sm overflow-hidden bg-card/50 backdrop-blur-sm">
                <CardHeader className="bg-muted/30 pb-6 border-b border-border/50">
                  <div className="flex items-center gap-2">
                    <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg text-white">
                      <Settings2 className="w-5 h-5" />
                    </div>
                    <CardTitle className="text-lg font-medium">{t('configuration')}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="p-6 space-y-8">
                  {/* Duration Settings */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Clock className="w-4 h-4" />
                      {t('clipDuration')}
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="minDuration">{t('minDuration')} (s)</Label>
                        <Input id="minDuration" name="minDuration" type="number" defaultValue="60" min="10" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="maxDuration">{t('maxDuration')} (s)</Label>
                        <Input id="maxDuration" name="maxDuration" type="number" defaultValue="110" min="10" />
                      </div>
                    </div>
                  </div>

                  <Separator />

                  {/* Mobile/Style Settings */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                        <Smartphone className="w-4 h-4" />
                        {t('mobileFormat')}
                      </div>
                      <Badge variant="outline">{t('verticalFormat')}</Badge>
                    </div>

                    <div className="flex items-center justify-between p-4 rounded-lg bg-muted/40 border">
                      <div className="space-y-0.5">
                        <Label className="text-base">{t('generateNoBackground')}</Label>
                        <p className="text-xs text-muted-foreground max-w-[250px]">{t('createThirdVariation')}</p>
                      </div>
                      <Switch checked={generateNoBackground} onCheckedChange={setGenerateNoBackground} />
                    </div>

                    {generateNoBackground && (
                      <div className="space-y-3 pt-2">
                        <div className="flex justify-between text-xs">
                          <span>{t('stricterMoreBlur')}</span>
                          <span className="text-muted-foreground font-mono">{blurredPillarboxThreshold.toFixed(2)}</span>
                          <span>{t('tolerantLessBlur')}</span>
                        </div>
                        <Slider
                          value={[blurredPillarboxThreshold]}
                          min={0.05}
                          max={0.5}
                          step={0.01}
                          onValueChange={([v]) => setBlurredPillarboxThreshold(v)}
                        />
                      </div>
                    )}
                  </div>

                  <Separator />

                  {/* System Settings */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label>{t('compilations')}</Label>
                      <Input name="numCompilations" type="number" defaultValue="1" min="1" disabled={isUnlimited} />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('maxReuse')}</Label>
                      <Input name="maxReuse" type="number" defaultValue="3" min="1" />
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Switch id="unlimited" checked={isUnlimited} onCheckedChange={setIsUnlimited} />
                    <Label htmlFor="unlimited">{t('generateUnlimited')}</Label>
                  </div>



                  <Button type="submit" size="lg" disabled={busy} className="w-full relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-r from-primary to-purple-600 opacity-80 group-hover:opacity-100 transition-opacity" />
                    <span className="relative flex items-center justify-center gap-2">
                      {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Brain className="w-5 h-5" />}
                      {t('generateCompilation')}
                    </span>
                  </Button>
                </CardContent>
              </Card>
            </form>
          )}
        </div>

        {/* Right Column: Info & Help */}
        <div className="lg:col-span-4 space-y-6">
          <Card className="border-border/50 shadow-sm bg-gradient-to-b from-card to-background">
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg text-purple-600 dark:text-purple-400">
                  <HelpCircle className="w-4 h-4" />
                </div>
                <CardTitle className="text-base">{t('howItWorks')}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="relative pl-4 space-y-6 border-l-2 border-muted">
                {[
                  { title: t('extractContent'), desc: t('extractContentDesc'), color: "bg-blue-500" },
                  { title: t('createClips'), desc: t('createClipsDesc'), color: "bg-green-500" },
                  { title: t('generateVariations'), desc: t('generateVariationsDesc'), color: "bg-purple-500" }
                ].map((step, i) => (
                  <div key={i} className="relative">
                    <div className={`absolute -left-[21px] top-1 w-3 h-3 rounded-full ${step.color} border-2 border-background`} />
                    <h4 className="font-medium text-sm">{step.title}</h4>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{step.desc}</p>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800/30 text-xs">
                <span className="font-semibold text-orange-700 dark:text-orange-400 block mb-1">{t('proTip')}</span>
                <span className="text-orange-600/80 dark:text-orange-300/80">
                  {t('proTipContent')}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
