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
    if (percent > 0 && percent < 100) return true
    const s = (status || '').toLowerCase()
    if (!s) return false
    return !["done", "error", "cancelled"].includes(s)
  }, [percent, status])

  return (
    <Card className="sticky top-4">
      <CardHeader>
        <CardTitle className="text-base">Job</CardTitle>
        <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
          <span>ID: {viewId}</span>
          <span>•</span>
          <span className="inline-flex items-center gap-1">
            Status: {viewStatus}
            {isActive ? <Loader2 className="size-3 animate-spin" aria-hidden /> : null}
          </span>
        </div>
      </CardHeader>
      <CardContent className="grid gap-2">
        <div className="mt-1 mb-1" aria-live="polite">
          <div className="sr-only">Progress {percent}%</div>
          <Progress value={percent} />
        </div>
        {steps.map((s) => (
          <div key={s.key} className="flex items-center gap-2 rounded-md border p-2">
            <Checkbox checked={!!s.done} aria-label={`${s.label} ${s.done ? "done" : "pending"}`} />
            <div className="flex-1 text-sm">{s.label}</div>
            <Badge variant={s.done ? "outline" : "secondary"} className="font-normal">
              {s.done ? "done" : "pending"}
            </Badge>
          </div>
        ))}
        {error ? (
          <div className="text-xs text-red-500">{error}</div>
        ) : null}
      </CardContent>
    </Card>
  )
}
