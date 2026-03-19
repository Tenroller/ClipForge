'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { type JobRecord } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

/** Statuses that indicate the job is finished and the SSE stream will close. */
const TERMINAL_STATUSES = new Set(['done', 'error', 'cancelled', 'completed', 'failed']);

type ConnectionState = 'connecting' | 'open' | 'closed' | 'fallback';

interface UseJobSSEOptions {
  /** Specific job ID to stream. If omitted, streams all jobs. */
  jobId?: string | null;
  /** Whether the hook is enabled. Defaults to true. */
  enabled?: boolean;
  /** Callback fired whenever a job_update event arrives. */
  onUpdate?: (job: Partial<JobRecord>) => void;
  /** Interval (ms) for REST polling fallback. Defaults to 3000. */
  fallbackInterval?: number;
}

interface UseJobSSEReturn {
  /** Current connection state. */
  connectionState: ConnectionState;
  /** The latest job data received via SSE (single-job mode only). */
  latestJob: Partial<JobRecord> | null;
}

/**
 * Hook that connects to the SSE endpoint for real-time job progress.
 *
 * Falls back to REST polling if SSE connection fails (e.g., browser doesn't
 * support EventSource, or the backend is behind a proxy that strips SSE).
 *
 * Updates the React Query cache so all consumers of `useJob` / `useJobs`
 * see fresh data immediately without extra network requests.
 */
export function useJobSSE(options: UseJobSSEOptions = {}): UseJobSSEReturn {
  const {
    jobId,
    enabled = true,
    onUpdate,
    fallbackInterval = 3000,
  } = options;

  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  const fallbackTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);

  const [connectionState, setConnectionState] = useState<ConnectionState>('closed');
  const [latestJob, setLatestJob] = useState<Partial<JobRecord> | null>(null);

  // Stable reference for the onUpdate callback
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  /**
   * Apply an incoming job_update to the React Query cache.
   */
  const applyUpdate = useCallback(
    (data: Partial<JobRecord>) => {
      const id = data.id;
      if (!id) return;

      // Update single-job cache
      queryClient.setQueryData<JobRecord | null>(['job', id], (prev) => {
        if (!prev) return data as JobRecord;
        return { ...prev, ...data };
      });

      // Update jobs list cache
      queryClient.setQueryData<JobRecord[]>(['jobs'], (prev) => {
        if (!prev) return prev as unknown as JobRecord[];
        return prev.map((j) => (j.id === id ? { ...j, ...data } : j));
      });

      setLatestJob(data);
      onUpdateRef.current?.(data);
    },
    [queryClient],
  );

  /**
   * Start REST polling as a fallback.
   */
  const startFallbackPolling = useCallback(() => {
    // Clean up any existing fallback
    if (fallbackTimerRef.current) {
      clearInterval(fallbackTimerRef.current);
    }

    setConnectionState('fallback');

    fallbackTimerRef.current = setInterval(async () => {
      try {
        if (jobId) {
          const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`, {
            credentials: 'include',
          });
          if (res.ok) {
            const job = await res.json();
            applyUpdate(job);

            // Stop polling if terminal
            if (job.status && TERMINAL_STATUSES.has(job.status)) {
              if (fallbackTimerRef.current) {
                clearInterval(fallbackTimerRef.current);
                fallbackTimerRef.current = null;
              }
              setConnectionState('closed');
            }
          }
        } else {
          const res = await fetch(`${API_BASE}/api/jobs?limit=50`, {
            credentials: 'include',
          });
          if (res.ok) {
            const data = await res.json();
            const jobs: JobRecord[] = Array.isArray(data?.jobs) ? data.jobs : [];
            queryClient.setQueryData(['jobs'], jobs);
          }
        }
      } catch {
        // Silently ignore fetch errors during fallback polling
      }
    }, fallbackInterval);
  }, [jobId, fallbackInterval, applyUpdate, queryClient]);

  /**
   * Stop everything: SSE connection, fallback timer, reconnect timer.
   */
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (fallbackTimerRef.current) {
      clearInterval(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  /**
   * Connect to the SSE endpoint.
   */
  const connect = useCallback(() => {
    cleanup();

    // Build URL
    const url = new URL(`${API_BASE}/api/jobs/stream`);
    if (jobId) {
      url.searchParams.set('job_id', jobId);
    }

    setConnectionState('connecting');

    const es = new EventSource(url.toString(), { withCredentials: true });
    eventSourceRef.current = es;

    es.addEventListener('open', () => {
      setConnectionState('open');
      reconnectAttemptRef.current = 0;
    });

    es.addEventListener('job_update', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as Partial<JobRecord>;
        applyUpdate(data);

        // If single-job mode and terminal, close the connection
        if (jobId && data.status && TERMINAL_STATUSES.has(data.status)) {
          es.close();
          eventSourceRef.current = null;
          setConnectionState('closed');
        }
      } catch {
        // Ignore malformed events
      }
    });

    es.addEventListener('heartbeat', () => {
      // Heartbeat received -- connection is alive. Nothing to do.
    });

    es.addEventListener('error', () => {
      // Close the broken connection
      es.close();
      eventSourceRef.current = null;

      // Exponential backoff for reconnection (max 3 attempts before fallback)
      const attempt = reconnectAttemptRef.current;
      if (attempt < 3) {
        reconnectAttemptRef.current = attempt + 1;
        const delay = Math.min(1000 * Math.pow(2, attempt), 8000);
        setConnectionState('connecting');
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        // Give up on SSE, switch to REST polling fallback
        startFallbackPolling();
      }
    });
  }, [jobId, applyUpdate, cleanup, startFallbackPolling]);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      setConnectionState('closed');
      return;
    }

    // For single-job mode, only connect if we have a job ID
    if (jobId === null || jobId === undefined) {
      // No jobId provided and not in "all jobs" mode? Check if caller explicitly passed undefined.
      // If options.jobId is explicitly undefined/null, don't start streaming.
      if ('jobId' in options && !options.jobId) {
        cleanup();
        setConnectionState('closed');
        return;
      }
    }

    connect();

    return () => {
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, jobId]);

  return { connectionState, latestJob };
}
