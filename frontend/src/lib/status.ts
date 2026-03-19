/**
 * Centralized status, workflow, and score color/icon utilities.
 * Uses design tokens (success, destructive, warning, info, accent, muted)
 * instead of hard-coded Tailwind colors, ensuring consistent light/dark mode.
 */

/** Status badge classes — background, text, and border using design tokens */
export function getStatusClasses(status: string): string {
  switch (status) {
    case 'completed':
    case 'done':
      return 'bg-success/10 text-success border-success/20';
    case 'error':
      return 'bg-destructive/10 text-destructive border-destructive/20';
    case 'processing':
    case 'running':
    case 'queued':
      return 'bg-info/10 text-info border-info/20';
    case 'cancelled':
      return 'bg-muted text-muted-foreground border-border';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
}

/** Solid status dot/indicator color */
export function getStatusDotColor(status: string): string {
  switch (status) {
    case 'completed':
    case 'done':
      return 'bg-success';
    case 'error':
      return 'bg-destructive';
    case 'processing':
    case 'running':
      return 'bg-info';
    case 'queued':
      return 'bg-warning';
    case 'cancelled':
      return 'bg-muted-foreground';
    default:
      return 'bg-muted-foreground';
  }
}

/** Icon text color for status indicators */
export function getStatusIconColor(status: string): string {
  switch (status) {
    case 'completed':
    case 'done':
      return 'text-success';
    case 'error':
      return 'text-destructive';
    case 'processing':
    case 'running':
      return 'text-info';
    case 'queued':
      return 'text-warning';
    case 'cancelled':
      return 'text-muted-foreground';
    default:
      return 'text-muted-foreground';
  }
}

/** Workflow badge classes — background, text, and border */
export function getWorkflowClasses(workflow: string): string {
  switch (workflow) {
    case 'moneyprinter':
      return 'bg-info/10 text-info border-info/20';
    case 'brainrot':
      return 'bg-accent/10 text-accent border-accent/20';
    case 'podcastclips':
      return 'bg-success/10 text-success border-success/20';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
}

/** Solid workflow color for chart dots, progress bars, etc. */
export function getWorkflowDotColor(workflow: string): string {
  switch (workflow) {
    case 'moneyprinter':
      return 'bg-info';
    case 'brainrot':
      return 'bg-warning';
    case 'podcastclips':
      return 'bg-success';
    default:
      return 'bg-muted-foreground';
  }
}

/** Score badge color for viral/quality scores (0-10) */
export function getScoreColor(score: number): string {
  if (score >= 9) return 'bg-success';
  if (score >= 8) return 'bg-success/80';
  if (score >= 7) return 'bg-warning';
  if (score >= 6) return 'bg-warning/80';
  return 'bg-destructive';
}

/** Feedback card classes — for success/error/warning feedback panels */
export function getFeedbackClasses(type: 'success' | 'error' | 'warning' | 'info'): {
  card: string;
  icon: string;
  title: string;
  text: string;
} {
  switch (type) {
    case 'success':
      return {
        card: 'border-success/20 bg-success/5',
        icon: 'text-success',
        title: 'text-success',
        text: 'text-success/80',
      };
    case 'error':
      return {
        card: 'border-destructive/20 bg-destructive/5',
        icon: 'text-destructive',
        title: 'text-destructive',
        text: 'text-destructive/80',
      };
    case 'warning':
      return {
        card: 'border-warning/20 bg-warning/5',
        icon: 'text-warning',
        title: 'text-warning',
        text: 'text-warning/80',
      };
    case 'info':
      return {
        card: 'border-info/20 bg-info/5',
        icon: 'text-info',
        title: 'text-info',
        text: 'text-info/80',
      };
  }
}
