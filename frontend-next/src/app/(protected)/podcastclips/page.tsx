'use client';

import { useState, useEffect } from 'react';
import { useJobs, useAvailableModels } from '@/hooks/use-jobs';
import JobStartedNotification from '@/components/job/JobStartedNotification';
import ResultPanel from '@/components/job/ResultPanel';
import { useToast } from '@/hooks/use-toast';
import type { JobRecord } from '@/lib/api';
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Sparkles, Video, Zap, Target } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export default function PodcastClipsPage() {
  const { toast } = useToast();
  const { data: recentJobs = [] } = useJobs({ limit: 10, refetchInterval: 5000 });
  const { data: models = [] } = useAvailableModels();

  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<JobRecord | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form state
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [aiModel, setAiModel] = useState('gemini-2.0-flash');
  const [whisperModel, setWhisperModel] = useState('base');
  const [targetClipCount, setTargetClipCount] = useState(7);
  const [minDuration, setMinDuration] = useState(30);
  const [maxDuration, setMaxDuration] = useState(60);
  const [subtitleFontSize, setSubtitleFontSize] = useState(40);

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
        toast({
          title: '🎉 Clips Generated!',
          description: `Successfully created ${currentJob.result?.clips_count || 'multiple'} viral clips`,
        });
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

    if (!youtubeUrl.trim()) {
      toast({
        title: 'YouTube URL Required',
        description: 'Please enter a valid YouTube podcast URL',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        youtubeUrl: youtubeUrl.trim(),
        aiModel,
        whisperModel,
        targetClipCount,
        minDuration,
        maxDuration,
        useGPU: true,
        subtitleFontSize,
        subtitleColor: '#FFFFFF',
        subtitleStrokeColor: '#000000',
        subtitleStrokeWidth: 2,
        viralFocusKeywords: []
      };

      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/api/podcastclips/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start job');
      }

      const data = await response.json();
      setCurrentJobId(data.jobId);

      toast({
        title: '🚀 Job Started',
        description: `Generating ${targetClipCount} viral clips from podcast`,
      });
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.message || 'Failed to start podcast clips generation',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg">
          <Sparkles className="h-8 w-8 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold">Podcast Clips</h1>
          <p className="text-muted-foreground">
            Generate viral short-form videos from podcasts with AI-powered moment detection
          </p>
        </div>
      </div>

      {/* Features Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-purple-500" />
              <div>
                <p className="font-semibold text-sm">AI Detection</p>
                <p className="text-xs text-muted-foreground">Viral moments</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Target className="h-5 w-5 text-blue-500" />
              <div>
                <p className="font-semibold text-sm">Face Tracking</p>
                <p className="text-xs text-muted-foreground">Smart cropping</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Zap className="h-5 w-5 text-yellow-500" />
              <div>
                <p className="font-semibold text-sm">Parallel Gen</p>
                <p className="text-xs text-muted-foreground">3x faster</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Video className="h-5 w-5 text-green-500" />
              <div>
                <p className="font-semibold text-sm">9:16 Format</p>
                <p className="text-xs text-muted-foreground">Social ready</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Generation Form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Generate Viral Clips</CardTitle>
              <CardDescription>
                Enter a YouTube podcast URL to automatically generate 5-10 viral short-form clips
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* YouTube URL */}
                <div className="space-y-2">
                  <Label htmlFor="youtubeUrl">YouTube Podcast URL *</Label>
                  <Input
                    id="youtubeUrl"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                {/* AI Model */}
                <div className="space-y-2">
                  <Label htmlFor="aiModel">AI Model for Viral Detection</Label>
                  <Select value={aiModel} onValueChange={setAiModel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {models.length > 0 ? (
                        models.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.name}
                          </SelectItem>
                        ))
                      ) : (
                        <>
                          <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash (Recommended)</SelectItem>
                          <SelectItem value="gemini-1.5-pro">Gemini 1.5 Pro</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>

                {/* Whisper Model */}
                <div className="space-y-2">
                  <Label htmlFor="whisperModel">Transcription Model</Label>
                  <Select value={whisperModel} onValueChange={setWhisperModel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tiny">Tiny (Fastest)</SelectItem>
                      <SelectItem value="base">Base (Recommended)</SelectItem>
                      <SelectItem value="small">Small (Better)</SelectItem>
                      <SelectItem value="medium">Medium (Best)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Target Clip Count */}
                <div className="space-y-2">
                  <Label htmlFor="targetClipCount">
                    Target Clip Count: <Badge variant="secondary">{targetClipCount}</Badge>
                  </Label>
                  <Slider
                    id="targetClipCount"
                    min={5}
                    max={10}
                    step={1}
                    value={[targetClipCount]}
                    onValueChange={(value) => setTargetClipCount(value[0])}
                    disabled={isSubmitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    AI will generate the best {targetClipCount} clips (5-10 range)
                  </p>
                </div>

                {/* Duration Range */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="minDuration">
                      Min Duration: <Badge variant="outline">{minDuration}s</Badge>
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
                      Max Duration: <Badge variant="outline">{maxDuration}s</Badge>
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
                    Subtitle Font Size: <Badge variant="secondary">{subtitleFontSize}px</Badge>
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

                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={isSubmitting || !!currentJobId}
                >
                  {isSubmitting ? 'Starting...' : currentJobId ? 'Processing...' : '🚀 Generate Viral Clips'}
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
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">How It Works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="space-y-2">
                  <p className="font-semibold">1. AI Analysis</p>
                  <p className="text-muted-foreground">
                    Gemini AI analyzes your podcast and identifies the most viral-worthy moments
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">2. Smart Cropping</p>
                  <p className="text-muted-foreground">
                    MediaPipe tracks faces for intelligent 9:16 cropping focused on the speaker
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">3. Hook Optimization</p>
                  <p className="text-muted-foreground">
                    Clips are trimmed to start with the most engaging hook for maximum retention
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">4. Audio Enhancement</p>
                  <p className="text-muted-foreground">
                    Automatic audio normalization and quality improvement
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-semibold">5. Thumbnails</p>
                  <p className="text-muted-foreground">
                    Auto-generated thumbnails for each clip, ready for social media
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
