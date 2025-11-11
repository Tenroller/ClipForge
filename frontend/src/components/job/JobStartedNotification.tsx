'use client';

import React, { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, Eye, Loader2 } from "lucide-react"

interface JobStartedNotificationProps {
  jobId: string
  workflow?: 'moneyprinter' | 'brainrot'
  // optional runtime status fields supplied by callers
  status?: string
  progress?: number
  currentStep?: string
  className?: string
  autoRedirect?: boolean
  redirectDelay?: number
}

export default function JobStartedNotification({
  jobId,
  workflow = 'moneyprinter',
  status,
  progress,
  currentStep,
  className,
  autoRedirect = true,
  redirectDelay = 3000
}: JobStartedNotificationProps) {
  const router = useRouter()

  const workflowLabel = workflow === 'brainrot' ? 'Brainrot Compilation' : 'AI Video Generation'
  const shortJobId = jobId.length > 8 ? `${jobId.substring(0, 8)}...` : jobId

  const handleMonitorJob = () => {
    router.push(`/job/${jobId}`)
  }

  // Auto-redirect to monitoring page after delay
  useEffect(() => {
    if (autoRedirect) {
      const timer = setTimeout(() => {
        router.push(`/job/${jobId}`)
      }, redirectDelay)

      return () => clearTimeout(timer)
    }
  }, [autoRedirect, redirectDelay, jobId, router])

  return (
    <Card className={`border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-800/30 ${className}`}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-3">
          <CheckCircle className="size-5 text-green-600" />
          {autoRedirect ? 'Job Started Successfully' : 'Job In Progress'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Job ID:</span>
            <code className="bg-muted px-2 py-1 rounded text-sm font-mono">
              {shortJobId}
            </code>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Workflow:</span>
            <Badge variant="outline">{workflowLabel}</Badge>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Status:</span>
            <div className="flex items-center gap-2">
              <Loader2 className="size-3 animate-spin text-blue-500" />
              <span className="text-sm font-medium">Processing...</span>
            </div>
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={handleMonitorJob} className="flex-1">
            <Eye className="size-4 mr-2" />
            Monitor Progress
          </Button>
        </div>

        {/* If callers supply runtime fields, show a compact status summary */}
        {(status || progress !== undefined || currentStep) && (
          <div className="mt-3 text-sm text-muted-foreground">
            {status && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Runtime Status:</span>
                <span className="font-medium">{status}</span>
              </div>
            )}
            {progress !== undefined && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Progress:</span>
                <span className="font-medium">{Math.round(progress)}%</span>
              </div>
            )}
            {currentStep && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Step:</span>
                <span className="font-medium">{currentStep}</span>
              </div>
            )}
          </div>
        )}

        {autoRedirect ? (
          <div className="text-xs text-center text-muted-foreground bg-blue-50 dark:bg-blue-950/20 p-3 rounded-lg border border-blue-200 dark:border-blue-800/30">
            <p className="flex items-center justify-center gap-2">
              <Loader2 className="size-3 animate-spin" />
              Redirecting to job monitoring in {Math.ceil(redirectDelay / 1000)} seconds...
            </p>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg">
            <p>
              This job is currently running in the background. Click &apos;Monitor Progress&apos; to view detailed progress and logs.
            </p>
          </div>
        )}

        {autoRedirect && (
          <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg">
            <p>
              Your job is now being processed in the background. You will be redirected to the monitoring page where you can track progress in real-time and view detailed logs.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
