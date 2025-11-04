/**
 * Format duration in seconds to a human-readable string
 * @param seconds - Duration in seconds
 * @returns Formatted string like "2m 45s", "1h 23m", "45s"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || seconds < 0) {
    return 'N/A'
  }

  if (seconds === 0) {
    return '0s'
  }

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60

  const parts = []

  if (hours > 0) {
    parts.push(`${hours}h`)
  }

  if (minutes > 0) {
    parts.push(`${minutes}m`)
  }

  if (remainingSeconds > 0 || parts.length === 0) {
    parts.push(`${remainingSeconds}s`)
  }

  return parts.join(' ')
}

/**
 * Format duration from timestamps
 * @param startedAt - ISO timestamp when job started
 * @param completedAt - ISO timestamp when job completed (optional, uses current time if not provided)
 * @returns Formatted duration string
 */
export function formatDurationFromTimestamps(
  startedAt: string | null | undefined,
  completedAt?: string | null | undefined
): string {
  if (!startedAt) {
    return 'N/A'
  }

  const startTime = new Date(startedAt).getTime()
  const endTime = completedAt ? new Date(completedAt).getTime() : Date.now()

  if (startTime > endTime) {
    return 'N/A'
  }

  const durationMs = endTime - startTime
  const durationSeconds = Math.floor(durationMs / 1000)

  return formatDuration(durationSeconds)
}
