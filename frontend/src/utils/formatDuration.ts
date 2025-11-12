/**
 * Formats duration in seconds to a human-readable string
 * @param seconds - Duration in seconds
 * @returns Formatted string like "21 secs" or "1 min 5 secs"
 */
export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) {
    return '0 secs';
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);

  if (minutes === 0) {
    return `${remainingSeconds} sec${remainingSeconds !== 1 ? 's' : ''}`;
  }

  if (remainingSeconds === 0) {
    return `${minutes} min${minutes !== 1 ? 's' : ''}`;
  }

  return `${minutes} min ${remainingSeconds} sec${remainingSeconds !== 1 ? 's' : ''}`;
}
