'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronDown, Film, Loader2, Plus, RefreshCw, FolderOpen, ArrowUpDown, Filter } from 'lucide-react';
import SourceVideoCard from '@/components/podcast/SourceVideoCard';
import ProjectClipsView from '@/components/podcast/ProjectClipsView';
import type { PodcastProject } from '@/lib/api';
import { listPodcastProjects, deletePodcastProject } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useRouter } from 'next/navigation';
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

export default function PodcastProjectsPage() {
  const t = useTranslations('projects');
  const { toast } = useToast();
  const router = useRouter();
  const [projects, setProjects] = useState<PodcastProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<'created_at' | 'clips_count' | 'title'>('created_at');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');

  // Selected project for detail view
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // Delete confirmation state
  const [projectToDelete, setProjectToDelete] = useState<PodcastProject | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const limit = 20;

  // Load projects
  const loadProjects = useCallback(async (reset = false) => {
    try {
      if (reset) {
        setLoading(true);
        setOffset(0);
      } else {
        setLoadingMore(true);
      }

      const currentOffset = reset ? 0 : offset;
      const data = await listPodcastProjects({
        limit,
        offset: currentOffset,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (reset) {
        setProjects(data.projects);
      } else {
        setProjects((prev) => [...prev, ...data.projects]);
      }

      setOffset(currentOffset + data.projects.length);
      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to load projects:', error);
      toast({
        title: t('error'),
        description: t('failedToLoad'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [offset, sortBy, sortOrder, toast, t]);

  // Initial load
  useEffect(() => {
    loadProjects(true);
  }, [sortBy, sortOrder]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle project click
  const handleProjectClick = (project: PodcastProject) => {
    setSelectedProjectId(project.id);
  };

  // Handle open external (YouTube)
  const handleOpenExternal = (project: PodcastProject) => {
    if (project.youtube_url) {
      window.open(project.youtube_url, '_blank');
    }
  };

  // Navigate to create new clip
  const handleNewVideo = () => {
    router.push('/podcastclips');
  };

  // Handle project deletion
  const handleDeleteProject = async () => {
    if (!projectToDelete) return;

    setIsDeleting(true);
    try {
      const result = await deletePodcastProject(projectToDelete.id);
      toast({
        title: t('deleteSuccess'),
        description: `${result.clips_deleted} clips deleted`,
      });
      // Remove from local state
      setProjects((prev) => prev.filter((p) => p.id !== projectToDelete.id));
      setProjectToDelete(null);
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast({
        title: t('error'),
        description: t('deleteError'),
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // If a project is selected, show the clips view
  if (selectedProjectId) {
    return (
      <div className="container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <ProjectClipsView
          projectId={selectedProjectId}
          onBack={() => setSelectedProjectId(null)}
          onNewVideo={handleNewVideo}
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <FolderOpen className="h-8 w-8 text-primary" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground text-lg">
            {t('description')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="icon"
            onClick={() => loadProjects(true)}
            disabled={loading}
            className="rounded-full"
            title={t('refresh')}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            size="lg"
            onClick={handleNewVideo}
            className="rounded-full shadow-lg shadow-primary/20 hover:shadow-primary/30"
          >
            <Plus className="h-5 w-5 mr-2" />
            {t('newProject')}
          </Button>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-muted/20 p-4 rounded-xl border border-border/50 mb-8 backdrop-blur-sm">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Filter className="w-4 h-4" />
          <span>{projects.length} Projects</span>
        </div>

        <div className="flex items-center gap-4 w-full sm:w-auto">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
              <SelectTrigger className="w-full sm:w-[160px] bg-background">
                <SelectValue placeholder={t('sortByPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="created_at">{t('date')}</SelectItem>
                <SelectItem value="clips_count">{t('clipsCount')}</SelectItem>
                <SelectItem value="title">{t('titleField')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select value={sortOrder} onValueChange={(v) => setSortOrder(v as typeof sortOrder)}>
              <SelectTrigger className="w-full sm:w-[130px] bg-background">
                <SelectValue placeholder={t('order')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">{t('descending')}</SelectItem>
                <SelectItem value="asc">{t('ascending')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Projects Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="overflow-hidden rounded-xl border-border/50">
              <Skeleton className="aspect-video w-full" />
              <div className="p-4 space-y-3">
                <div className="flex justify-between items-start">
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-4 w-12 rounded-full" />
                </div>
                <Skeleton className="h-4 w-1/2" />
                <div className="pt-4 flex gap-2">
                  <Skeleton className="h-9 w-full rounded-md" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <Card className="border-border/50 bg-muted/10 border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="size-20 rounded-full bg-primary/10 flex items-center justify-center mb-6 animate-pulse">
              <Film className="size-10 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-2">{t('noProjects')}</h3>
            <p className="text-muted-foreground max-w-md mb-8">
              {t('createFirstProject')}
            </p>
            <Button
              size="lg"
              onClick={handleNewVideo}
              className="rounded-full px-8"
            >
              <Plus className="h-5 w-5 mr-2" />
              {t('createProject')}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-in fade-in duration-500">
            {projects.map((project) => (
              <SourceVideoCard
                key={project.id}
                project={project}
                onClick={() => handleProjectClick(project)}
                onOpenExternal={() => handleOpenExternal(project)}
                onDelete={() => setProjectToDelete(project)}
              />
            ))}
          </div>

          {/* Load More Button */}
          {hasMore && (
            <div className="flex justify-center pt-12 pb-8">
              <Button
                variant="outline"
                size="lg"
                onClick={() => loadProjects(false)}
                disabled={loadingMore}
                className="rounded-full px-8"
              >
                {loadingMore ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    {t('loading')}
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4 mr-2" />
                    {t('loadMore')}
                  </>
                )}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!projectToDelete} onOpenChange={(open) => !open && setProjectToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {projectToDelete && t('confirmDeleteDescription', { title: projectToDelete.title, clips: projectToDelete.clips_count })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteProject}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('deleting')}
                </>
              ) : (
                t('delete')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
