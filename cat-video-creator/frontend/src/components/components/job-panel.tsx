"use client"

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Checkbox } from "@/components/components/ui/checkbox"
import { Badge } from "@/components/components/ui/badge"
import { Progress } from "@/components/components/ui/progress"
import { Loader2 } from "lucide-react"

export type JobStep = {
  key: string
  label: string
  done: boolean
  active?: boolean
}

export type JobPanelProps = {
  jobId?: string | null
  status?: string | null
  steps: JobStep[]
  error?: string | null
}

export default function JobPanel({ jobId, status, steps, error }: JobPanelProps) {
  const viewId = useMemo(() => jobId || "—", [jobId])
  const viewStatus = useMemo(() => status || "—", [status])
  const total = steps.length || 1
  const completed = steps.filter((s) => s.done).length
  const percent = Math.round((completed / total) * 100)
  const isActive = useMemo(() => {
    // If there's no jobId, there's no active job
    if (!jobId) return false
    if (percent > 0 && percent < 100) return true
    const s = (status || '').toLowerCase()
    if (!s) return false
    return !["done", "error", "cancelled"].includes(s)
  }, [percent, status, jobId])

  return (
    <Card className="lg:sticky lg:top-4 enhanced-card">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-3">
          <div className="size-8 rounded-lg bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center">
            {isActive ? (
              <Loader2 className="size-4 text-white animate-spin" />
            ) : (
              <div className="size-2 bg-white rounded-full" />
            )}
          </div>
          Job Progress
        </CardTitle>
        <div className="text-xs text-muted-foreground mt-2 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">ID:</span>
            <code className="px-2 py-0.5 bg-muted/50 rounded text-[10px] font-mono">{viewId}</code>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium">Status:</span>
            <Badge 
              variant={viewStatus === 'done' ? 'default' : isActive ? 'secondary' : 'outline'}
              className="text-[10px] h-5"
            >
              {viewStatus}
              {isActive && <Loader2 className="size-2 ml-1 animate-spin" />}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{percent}%</span>
          </div>
          <div className="sr-only" aria-live="polite">Progress {percent}%</div>
          <Progress value={percent} className="h-2" />
        </div>
        
        <div className="space-y-2">
          {steps.map((s, index) => (
            <div 
              key={s.key} 
              className={`flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 ${
                s.done 
                  ? 'bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800/50' 
                  : s.active
                  ? 'bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800/50'
                  : 'bg-muted/30 border-border/50'
              }`}
            >
              <div className="relative">
                <div className={`size-6 rounded-full border-2 flex items-center justify-center transition-all ${
                  s.done 
                    ? 'bg-green-500 border-green-500 text-white' 
                    : s.active
                    ? 'bg-blue-500 border-blue-500 text-white'
                    : 'border-muted-foreground/30 bg-background'
                }`}>
                  {s.done ? (
                    <svg className="size-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : s.active ? (
                    <Loader2 className="size-3 animate-spin" />
                  ) : (
                    <span className="text-xs font-medium text-muted-foreground">{index + 1}</span>
                  )}
                </div>
                {index < steps.length - 1 && (
                  <div className={`absolute top-6 left-3 w-0.5 h-4 ${
                    s.done ? 'bg-green-500' : s.active ? 'bg-blue-500' : 'bg-border'
                  }`} />
                )}
              </div>
              <div className="flex-1">
                <div className={`text-sm font-medium ${
                  s.done 
                    ? 'text-green-700 dark:text-green-300' 
                    : s.active 
                    ? 'text-blue-700 dark:text-blue-300'
                    : 'text-foreground'
                }`}>
                  {s.label}
                </div>
              </div>
              <Badge 
                variant={s.done ? 'default' : s.active ? 'secondary' : 'outline'} 
                className={`text-xs font-normal ${
                  s.done 
                    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' 
                    : s.active
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                    : ''
                }`}
              >
                {s.done ? 'completed' : s.active ? 'in progress' : 'pending'}
              </Badge>
            </div>
          ))}
        </div>
        
        {error ? (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 dark:bg-red-950/30 dark:border-red-800/50" role="alert">
            <div className="flex items-center gap-2 text-red-700 dark:text-red-300">
              <div className="size-4 rounded-full bg-red-500 flex items-center justify-center" aria-hidden="true">
                <span className="text-[10px] text-white font-bold">!</span>
              </div>
              <span className="text-xs font-medium">{error}</span>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
