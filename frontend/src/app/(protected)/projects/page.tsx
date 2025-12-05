'use client';

import { useState, useEffect, useCallback } from 'react';
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
import { listPodcastProjects } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useRouter } from 'next/navigation';

export default function PodcastProjectsPage() {
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
        title: 'Erro',
        description: 'Falha ao carregar projetos',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [offset, sortBy, sortOrder, toast]);

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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in-up">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="inline-block">
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
              PROJETOS RECENTES
            </h1>
            <div className="h-1 w-24 bg-gradient-to-r from-primary to-accent rounded-full mt-2" />
          </div>
          <p className="text-base text-muted-foreground max-w-2xl">
            Gerencie seus projetos de clips de podcast. Clique em um projeto para ver e editar os clips gerados.
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
            className="bg-purple-600 hover:bg-purple-700 text-white"
            onClick={handleNewVideo}
          >
            <Plus className="h-4 w-4 mr-2" />
            Novo Projeto
          </Button>
        </div>
      </div>

      {/* Sorting */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Ordenar por:</span>
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Ordenar por" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="created_at">Data</SelectItem>
              <SelectItem value="clips_count">Quantidade de Clips</SelectItem>
              <SelectItem value="title">Titulo</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Select value={sortOrder} onValueChange={(v) => setSortOrder(v as typeof sortOrder)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Ordem" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="desc">Decrescente</SelectItem>
              <SelectItem value="asc">Crescente</SelectItem>
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
                Nenhum projeto encontrado
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Crie seu primeiro projeto de clips de podcast
              </p>
              <Button
                className="mt-6 bg-purple-600 hover:bg-purple-700 text-white"
                onClick={handleNewVideo}
              >
                <Plus className="h-4 w-4 mr-2" />
                Criar Projeto
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
                    Carregando...
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4 mr-2" />
                    Carregar Mais
                  </>
                )}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
