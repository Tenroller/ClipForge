'use client';

import { useQuery, useMutation, useQueryClient, type Query } from '@tanstack/react-query';
import {
  listJobs,
  getJob,
  cancelJob,
  remakeJob,
  generateMoneyPrinterVideo,
  generateBrainrotVideo,
  getAvailableVoices,
  getJobLineage,
  getResumableJobs,
  resumeJob,
  type JobRecord,
} from '@/lib/api';

const JOBS_QUERY_KEY = ['jobs'];
const JOBS_FETCH_LIMIT = 50;

/**
 * Hook to fetch all jobs with optional polling.
 * All consumers share a single query to avoid duplicate network requests.
 */
export function useJobs(options?: {
  limit?: number;
  refetchInterval?: number | false | ((query: Query<JobRecord[]>) => number | false);
}) {
  const limit = options?.limit;
  return useQuery<JobRecord[]>({
    queryKey: JOBS_QUERY_KEY,
    queryFn: () => listJobs(JOBS_FETCH_LIMIT),
    refetchInterval: options?.refetchInterval,
    select: limit ? (data) => data.slice(0, limit) : undefined,
  });
}

/**
 * Hook to fetch a single job with automatic polling for active jobs
 */
export function useJob(jobId: string | undefined | null, options?: {
  refetchInterval?: number | false;
}) {
  return useQuery<JobRecord | null>({
    queryKey: ['job', jobId],
    queryFn: () => (jobId ? getJob(jobId) : null),
    enabled: !!jobId,
    refetchInterval: options?.refetchInterval ?? ((query) => {
      // Auto-poll active jobs every 2 seconds
      const data = query.state.data;
      if (data && ['queued', 'processing', 'running'].includes(data.status)) {
        return 2000;
      }
      // Don't poll completed/failed jobs
      return false;
    }),
  });
}

/**
 * Hook to cancel a job
 */
export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cancelJob,
    onSuccess: (data) => {
      // Invalidate job queries to refresh
      queryClient.invalidateQueries({ queryKey: ['job', data.jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

/**
 * Hook to remake a job
 */
export function useRemakeJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: remakeJob,
    onSuccess: (data) => {
      // Invalidate job queries to refresh
      queryClient.invalidateQueries({ queryKey: ['job', data.job_id] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

/**
 * Hook to generate MoneyPrinter video
 */
export function useGenerateMoneyPrinterVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: generateMoneyPrinterVideo,
    onSuccess: (data) => {
      // Invalidate jobs list to include new job
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Pre-fetch the new job
      queryClient.prefetchQuery({
        queryKey: ['job', data.jobId],
        queryFn: () => getJob(data.jobId),
      });
    },
  });
}

/**
 * Hook to generate Brainrot video
 */
export function useGenerateBrainrotVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: generateBrainrotVideo,
    onSuccess: (data) => {
      // Invalidate jobs list to include new job
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Pre-fetch the new job
      queryClient.prefetchQuery({
        queryKey: ['job', data.jobId],
        queryFn: () => getJob(data.jobId),
      });
    },
  });
}

/**
 * Hook to get active (in-progress) jobs
 */
export function useActiveJobs(options?: { refetchInterval?: number }) {
  const { data: jobs = [] } = useJobs({
    limit: 100,
    refetchInterval: options?.refetchInterval ?? 5000, // Poll every 5 seconds
  });

  return jobs.filter((job) =>
    ['queued', 'processing', 'running'].includes(job.status)
  );
}

/**
 * Hook to check if there are any active jobs
 */
export function useHasActiveJobs() {
  const activeJobs = useActiveJobs();
  return activeJobs.length > 0;
}

/**
 * Hook to fetch available voices
 */
export function useAvailableVoices() {
  return useQuery({
    queryKey: ['voices'],
    queryFn: getAvailableVoices,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
}

/**
 * Hook to fetch job lineage (ancestors and descendants)
 */
export function useJobLineage(jobId: string | undefined | null) {
  return useQuery({
    queryKey: ['job-lineage', jobId],
    queryFn: () => (jobId ? getJobLineage(jobId) : null),
    enabled: !!jobId,
    staleTime: 30 * 1000, // Cache for 30 seconds
  });
}

/**
 * Hook to fetch resumable jobs
 */
export function useResumableJobs() {
  return useQuery({
    queryKey: ['resumable-jobs'],
    queryFn: getResumableJobs,
    staleTime: 1 * 60 * 1000, // Cache for 1 minute
  });
}

/**
 * Hook to resume a job
 */
export function useResumeJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: resumeJob,
    onSuccess: (data) => {
      // Invalidate resumable jobs list
      queryClient.invalidateQueries({ queryKey: ['resumable-jobs'] });
      // Invalidate jobs list to include resumed job
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Pre-fetch the resumed job
      queryClient.prefetchQuery({
        queryKey: ['job', data.job_id],
        queryFn: () => getJob(data.job_id),
      });
    },
  });
}
