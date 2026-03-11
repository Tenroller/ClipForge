'use client';

import { useEffect, useRef } from 'react';
import { useJobs } from '@/hooks/use-jobs';
import { addNotification } from '@/hooks/useNotifications';

/**
 * Background component that watches for job status transitions
 * (completed / failed) and creates persistent notifications.
 *
 * Must be rendered inside the React Query provider.
 */

const TERMINAL_STATUSES = ['done', 'completed', 'failed', 'error', 'cancelled'];
const ACTIVE_STATUSES = ['queued', 'processing', 'running'];

function getWorkflowLabel(workflow: string | undefined): string {
  switch (workflow) {
    case 'moneyprinter':
      return 'AI Video';
    case 'brainrot':
      return 'Compilation';
    case 'podcastclips':
      return 'Podcast Clips';
    default:
      return workflow || 'Job';
  }
}

export function JobNotificationWatcher() {
  // Track which jobs we've already seen as terminal so we don't duplicate
  const seenTerminalRef = useRef<Set<string>>(new Set());
  // Track jobs that were previously active (so we only notify on transitions)
  const previousActiveRef = useRef<Set<string>>(new Set());
  const isFirstRenderRef = useRef(true);

  const { data: jobs } = useJobs({ refetchInterval: 5000 });

  useEffect(() => {
    if (!jobs || jobs.length === 0) return;

    // On first render, seed the seen set with already-terminal jobs
    // so we don't blast the user with old notifications.
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      for (const job of jobs) {
        if (TERMINAL_STATUSES.includes(job.status)) {
          seenTerminalRef.current.add(job.id);
        }
        if (ACTIVE_STATUSES.includes(job.status)) {
          previousActiveRef.current.add(job.id);
        }
      }
      return;
    }

    const currentActive = new Set<string>();

    for (const job of jobs) {
      if (ACTIVE_STATUSES.includes(job.status)) {
        currentActive.add(job.id);
      }

      // Only notify for jobs that transitioned to terminal AND were previously active
      if (
        TERMINAL_STATUSES.includes(job.status) &&
        !seenTerminalRef.current.has(job.id) &&
        previousActiveRef.current.has(job.id)
      ) {
        seenTerminalRef.current.add(job.id);
        const label = getWorkflowLabel(job.workflow);
        const shortId = job.id.length > 8 ? `${job.id.substring(0, 8)}...` : job.id;

        if (job.status === 'done' || job.status === 'completed') {
          addNotification({
            title: `${label} completed`,
            description: `Job ${shortId} finished successfully.`,
            type: 'success',
            jobId: job.id,
          });
        } else if (job.status === 'failed' || job.status === 'error') {
          addNotification({
            title: `${label} failed`,
            description: job.error_message
              ? `Job ${shortId}: ${job.error_message}`
              : `Job ${shortId} failed.`,
            type: 'error',
            jobId: job.id,
          });
        } else if (job.status === 'cancelled') {
          addNotification({
            title: `${label} cancelled`,
            description: `Job ${shortId} was cancelled.`,
            type: 'info',
            jobId: job.id,
          });
        }
      }
    }

    previousActiveRef.current = currentActive;
  }, [jobs]);

  // This component renders nothing – it just watches
  return null;
}
