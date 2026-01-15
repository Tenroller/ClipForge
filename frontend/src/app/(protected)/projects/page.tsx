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
import { ChevronDown, Film, Loader2, Plus, RefreshCw } from 'lucide-react';
import SourceVideoCard from '@/components/podcast/SourceVideoCard';
import ProjectClipsView from '@/components/podcast/ProjectClipsView';
import type { PodcastProject } from '@/lib/api';
import { listPodcastProjects, deletePodcastProject } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useRouter } from 'next/navigation';

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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
        <ProjectClipsView
          projectId={selectedProjectId}
          onBack={() => setSelectedProjectId(null)}
          onNewVideo={handleNewVideo}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t('description')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadProjects(true)}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
          <Button
            size="sm"
            onClick={handleNewVideo}
          >
            <Plus className="h-4 w-4 mr-2" />
            {t('newProject')}
          </Button>
        </div>
      </div>

      {/* Sorting */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{t('sortBy')}</span>
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder={t('sortByPlaceholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="created_at">{t('date')}</SelectItem>
              <SelectItem value="clips_count">{t('clipsCount')}</SelectItem>
              <SelectItem value="title">{t('titleField')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Select value={sortOrder} onValueChange={(v) => setSortOrder(v as typeof sortOrder)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder={t('order')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="desc">{t('descending')}</SelectItem>
              <SelectItem value="asc">{t('ascending')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Projects Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="overflow-hidden rounded-2xl">
              <Skeleton className="aspect-video w-full" />
              <div className="p-4 space-y-3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            </Card>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <Card className="border rounded-xl bg-card/50 backdrop-blur-sm shadow-md">
          <CardContent className="p-12">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
                <Film className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="text-lg font-medium text-muted-foreground">
                {t('noProjects')}
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                {t('createFirstProject')}
              </p>
              <Button
                className="mt-6 bg-purple-600 hover:bg-purple-700 text-white"
                onClick={handleNewVideo}
              >
                <Plus className="h-4 w-4 mr-2" />
                {t('createProject')}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
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
            <div className="flex justify-center pt-8">
              <Button
                variant="outline"
                onClick={() => loadProjects(false)}
                disabled={loadingMore}
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
      {projectToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-xl p-6 max-w-md mx-4 shadow-2xl border">
            <h3 className="text-lg font-semibold mb-2">{t('confirmDelete')}</h3>
            <p className="text-muted-foreground text-sm mb-4">
              {t('confirmDeleteDescription', { title: projectToDelete.title, clips: projectToDelete.clips_count })}
            </p>
            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => setProjectToDelete(null)}
                disabled={isDeleting}
              >
                {t('cancel')}
              </Button>
              <Button
                variant="destructive"
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
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
