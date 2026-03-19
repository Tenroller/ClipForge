'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ArrowLeft, ArrowUpDown, CheckSquare, Filter, Plus, Loader2, Scissors } from 'lucide-react';
import { EmptyState } from '@/components/ui/empty-state';
import ClipCard from './ClipCard';
import type { PodcastClip, PodcastProjectDetail } from '@/lib/api';
import {
  getPodcastProject,
  updateClipMetadata,
  deleteClip,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useJob } from '@/hooks/use-jobs';

interface ProjectClipsViewProps {
  projectId: string;
  onBack: () => void;
  onNewVideo?: () => void;
}

const STEP_KEYS = [
  'initialization',
  'download',
  'transcription',
  'speaker_diarization',
  'ai_analysis',
  'scoring',
  'hook_optimization',
  'face_detection',
  'speaker_detection',
  'clip_generation',
  'finalization',
  'post_processing',
  'completed',
] as const;

export default function ProjectClipsView({
  projectId,
  onBack,
  onNewVideo,
}: ProjectClipsViewProps) {
  const { toast } = useToast();
  const t = useTranslations('projectClipsView');
  const [project, setProject] = useState<PodcastProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'score' | 'time' | 'duration'>('score');
  const [filterBy, setFilterBy] = useState<'all' | 'liked' | 'disliked' | 'unrated'>('all');
  const [selectionMode, setSelectionMode] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [clipToDelete, setClipToDelete] = useState<PodcastClip | null>(null);

  // Fetch job details to show progress when job is still running
  const { data: job } = useJob(projectId, {
    refetchInterval: 3000, // Refresh every 3 seconds
  });

  // Load project data
  const loadProject = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getPodcastProject(projectId);
      setProject(data);
    } catch (error) {
      console.error('Failed to load project:', error);
      toast({
        title: t('error'),
        description: t('failedLoadProject'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [projectId, toast, t]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  // Auto-reload project when job completes
  useEffect(() => {
    if (job && (job.status === 'done' || job.status === 'completed')) {
      loadProject();
    }
  }, [job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sort clips
  const getSortedClips = useCallback(() => {
    if (!project?.clips) return [];

    let clips = [...project.clips];

    // Apply filter
    if (filterBy === 'liked') {
      clips = clips.filter((c) => c.likes > 0);
    } else if (filterBy === 'disliked') {
      clips = clips.filter((c) => c.dislikes > 0);
    } else if (filterBy === 'unrated') {
      clips = clips.filter((c) => c.likes === 0 && c.dislikes === 0);
    }

    // Apply sort
    switch (sortBy) {
      case 'score':
        return clips.sort((a, b) => b.viral_score - a.viral_score);
      case 'time':
        return clips.sort((a, b) => a.time_interval.start - b.time_interval.start);
      case 'duration':
        return clips.sort(
          (a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0)
        );
      default:
        return clips;
    }
  }, [project?.clips, sortBy, filterBy]);

  // Handle like
  const handleLike = async (clip: PodcastClip) => {
    try {
      const newLikes = clip.likes > 0 ? 0 : 1;
      await updateClipMetadata(projectId, clip.id, {
        likes: newLikes,
        dislikes: 0,
      });
      loadProject();
      toast({
        title: newLikes > 0 ? t('clipLiked') : t('likeRemoved'),
        description: newLikes > 0 ? t('clipMarkedGood') : t('likeRemovedDesc'),
      });
    } catch (error) {
      console.error('Failed to like clip:', error);
      toast({
        title: t('error'),
        description: t('failedLikeClip'),
        variant: 'destructive',
      });
    }
  };

  // Handle dislike
  const handleDislike = async (clip: PodcastClip) => {
    try {
      const newDislikes = clip.dislikes > 0 ? 0 : 1;
      await updateClipMetadata(projectId, clip.id, {
        dislikes: newDislikes,
        likes: 0,
      });
      loadProject();
      toast({
        title: newDislikes > 0 ? t('clipDisliked') : t('dislikeRemoved'),
        description: newDislikes > 0 ? t('clipMarkedBad') : t('dislikeRemovedDesc'),
      });
    } catch (error) {
      console.error('Failed to dislike clip:', error);
      toast({
        title: t('error'),
        description: t('failedDislikeClip'),
        variant: 'destructive',
      });
    }
  };

  // Handle delete
  const handleDelete = async (clip: PodcastClip) => {
    setClipToDelete(clip);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!clipToDelete) return;

    try {
      await deleteClip(projectId, clipToDelete.id, true);
      loadProject();
      toast({
        title: t('clipDeleted'),
        description: t('clipDeletedSuccess'),
      });
    } catch (error) {
      console.error('Failed to delete clip:', error);
      toast({
        title: t('error'),
        description: t('failedDeleteClip'),
        variant: 'destructive',
      });
    } finally {
      setDeleteDialogOpen(false);
      setClipToDelete(null);
    }
  };

  // Helper to calculate progress from job data
  const getJobProgress = () => {
    if (!job) return null;

    const steps = STEP_KEYS.map((key) => ({
      key,
      label: t(`steps.${key}`),
    }));

    const currentStepIndex = steps.findIndex(s => s.key === job.current_step);
    const currentStepLabel = currentStepIndex >= 0 ? steps[currentStepIndex].label : (job.current_step || '');
    const progress = job.progress ?? (currentStepIndex >= 0 ? Math.round(((currentStepIndex + 1) / steps.length) * 100) : 0);

    return {
      progress,
      currentStep: currentStepLabel,
      status: job.status,
    };
  };

  const sortedClips = getSortedClips();
  const jobProgress = getJobProgress();
  const isJobRunning = job && ['queued', 'running', 'processing'].includes(job.status);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-muted-foreground">{t('projectNotFound')}</p>
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          {t('back')}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={onBack}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-2xl font-bold text-primary line-clamp-2">
              {project.title} ({project.clips_count})
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 pl-12 sm:pl-0">
          {onNewVideo && (
            <Button onClick={onNewVideo}>
              <Plus className="h-4 w-4 mr-2" />
              {t('newVideo')}
            </Button>
          )}
          <Button
            variant={selectionMode ? 'default' : 'outline'}
            onClick={() => {
              setSelectionMode(!selectionMode);
            }}
          >
            <CheckSquare className="h-4 w-4 mr-2" />
            {t('select')}
          </Button>
        </div>
      </div>

      {/* Filters and Sorting */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={filterBy} onValueChange={(v) => setFilterBy(v as typeof filterBy)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t('filter')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('filterAll')}</SelectItem>
              <SelectItem value="liked">{t('filterLiked')}</SelectItem>
              <SelectItem value="disliked">{t('filterDisliked')}</SelectItem>
              <SelectItem value="unrated">{t('filterUnrated')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t('sort')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="score">{t('sortByScore')}</SelectItem>
              <SelectItem value="time">{t('sortByTime')}</SelectItem>
              <SelectItem value="duration">{t('sortByDuration')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Clips Grid */}
      {sortedClips.length === 0 ? (
        isJobRunning && jobProgress ? (
          // Show job progress when job is running and no clips yet
          <Card className="border rounded-xl bg-card">
            <CardContent className="p-8">
              <div className="space-y-6">
                <div className="flex items-center justify-center gap-3">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  <h3 className="text-xl font-semibold">{t('processingVideo')}</h3>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t('progress')}</span>
                    <span className="font-medium">{jobProgress.progress}%</span>
                  </div>
                  <Progress value={jobProgress.progress} className="h-2" />
                </div>

                <div className="text-center space-y-2">
                  <p className="text-sm font-medium text-primary">
                    {t('currentStep', { step: jobProgress.currentStep })}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t('clipsAppearWhenDone')}
                  </p>
                </div>

                {job?.started_at && (
                  <div className="text-center text-xs text-muted-foreground">
                    {t('startedAt', { time: new Date(job.started_at).toLocaleString() })}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          // Show "no clips found" message when job is not running
          <EmptyState
            icon={Scissors}
            title={t('noClipsFound')}
            description={
              filterBy !== 'all'
                ? t('tryAdjustFilters')
                : t('noClipsGenerated')
            }
            className="min-h-[300px]"
          />
        )
      ) : (
        <div className="grid grid-cols-1 min-[400px]:grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {sortedClips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              projectId={projectId}
              onRender={() => { }}
              onDelete={() => handleDelete(clip)}
              onLike={() => handleLike(clip)}
              onDislike={() => handleDislike(clip)}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteClipTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteClipWarning')}
              <br />
              <br />
              <strong>{clipToDelete?.title || clipToDelete?.filename}</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t('deleteConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
