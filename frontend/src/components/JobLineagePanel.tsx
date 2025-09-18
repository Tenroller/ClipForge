import React, { useEffect, useState, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/components/ui/card'
import { Badge } from '@/components/components/ui/badge'
import { Button } from '@/components/components/ui/button'
import { FaSitemap, FaSpinner, FaRedo, FaCheckCircle, FaTimesCircle, FaPause, FaClock, FaChevronRight, FaCopy } from 'react-icons/fa'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import type { UseJobManagerReturn } from '@/hooks/useJobManager'

interface LineageRecord {
  id: string
  status?: string
  resume_attempt?: number
  resumed_from?: string
  children_count?: number
}

interface JobLineagePanelProps {
  jobId: string
  jobManager: UseJobManagerReturn
  className?: string
}

export default function JobLineagePanel({ jobId, jobManager, className }: JobLineagePanelProps) {
  const [ancestors, setAncestors] = useState<LineageRecord[]>([])
  const [descendants, setDescendants] = useState<LineageRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetched, setLastFetched] = useState<number | null>(null)
  const navigate = useNavigate()

  const loadLineage = useCallback(async (force = false) => {
    if (!jobId) return
    setLoading(true)
    setError(null)
    try {
      const data = await jobManager.fetchJobLineage(jobId, { force })
      setAncestors(data.ancestors || [])
      setDescendants(data.descendants || [])
      setLastFetched(Date.now())
    } catch (e: any) {
      setError(e?.message || 'Failed to load lineage')
    } finally {
      setLoading(false)
    }
  }, [jobId, jobManager])

  useEffect(() => {
    loadLineage(false)
  }, [jobId, loadLineage])

  const statusBadge = (status?: string) => {
    switch (status) {
      case 'done':
        return <Badge variant="secondary" className="gap-1"><FaCheckCircle className="size-3" /> done</Badge>
      case 'error':
        return <Badge variant="destructive" className="gap-1"><FaTimesCircle className="size-3" /> error</Badge>
      case 'cancelled':
        return <Badge variant="outline" className="gap-1"><FaPause className="size-3" /> cancelled</Badge>
      case 'running':
        return <Badge variant="default" className="gap-1"><FaSpinner className="size-3 animate-spin" /> running</Badge>
      case 'queued':
        return <Badge variant="outline" className="gap-1"><FaClock className="size-3" /> queued</Badge>
      default:
        return <Badge variant="outline">unknown</Badge>
    }
  }

  const shortId = (id: string) => id.slice(0, 8)

  const copyId = (id: string) => {
    try {
      navigator.clipboard.writeText(id)
      toast.success('Copied job ID to clipboard')
    } catch {}
  }

  const chain = [...ancestors, { id: jobId }]

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <FaSitemap className="size-5" />
            Lineage
          </CardTitle>
          <CardDescription>
            Ancestry & resume attempts for this job
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {lastFetched && (
            <span className="text-xs text-muted-foreground hidden md:inline">
              {new Date(lastFetched).toLocaleTimeString()}
            </span>
          )}
          <Button size="sm" variant="outline" onClick={() => loadLineage(false)} disabled={loading}>
            <FaRedo className={`size-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" variant="ghost" onClick={() => loadLineage(true)} disabled={loading} title="Force reload (bypass cache)">
            <FaRedo className={`size-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <div className="p-3 border border-red-200 bg-red-50 rounded text-sm text-red-700 dark:bg-red-950/30 dark:border-red-800/50">
            {error}
          </div>
        )}

        {/* Ancestor Chain */}
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">Ancestor Chain</div>
          {loading && chain.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><FaSpinner className="size-4 animate-spin" /> Loading lineage...</div>
          ) : chain.length === 1 && ancestors.length === 0 ? (
            <div className="text-sm text-muted-foreground">This job has no ancestors (root of its chain).</div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {chain.map((rec, idx) => {
                const isCurrent = rec.id === jobId
                const ancestorMeta = ancestors.find(a => a.id === rec.id)
                return (
                  <React.Fragment key={rec.id}>
                    <div className={`group flex items-center gap-2 px-2 py-1 rounded border text-xs font-mono cursor-pointer transition ${isCurrent ? 'bg-blue-50 dark:bg-blue-950/30 border-blue-300 dark:border-blue-700' : 'bg-muted/40 border-border/50 hover:bg-muted'} `}
                      onClick={() => { if (!isCurrent) navigate(`/jobs/${rec.id}`) }}
                      title={isCurrent ? 'Current job' : 'View this ancestor job'}
                    >
                      <span>{shortId(rec.id)}</span>
                      {ancestorMeta?.resume_attempt && ancestorMeta.resume_attempt > 1 && (
                        <Badge variant="outline" className="text-[10px] py-0 px-1">#{ancestorMeta.resume_attempt}</Badge>
                      )}
                      {isCurrent && <Badge variant="secondary" className="text-[10px] py-0 px-1">current</Badge>}
                      <button onClick={(e) => { e.stopPropagation(); copyId(rec.id) }} className="opacity-40 group-hover:opacity-100 transition" title="Copy job ID">
                        <FaCopy className="size-3" />
                      </button>
                    </div>
                    {idx < chain.length - 1 && <FaChevronRight className="size-3 text-muted-foreground" />}
                  </React.Fragment>
                )
              })}
            </div>
          )}
        </div>

        {/* Descendants */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Descendants</div>
            {descendants.length > 0 && (
              <div className="text-xs text-muted-foreground">{descendants.length} job{descendants.length === 1 ? '' : 's'}</div>
            )}
          </div>
          {loading && descendants.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><FaSpinner className="size-4 animate-spin" /> Loading descendants...</div>
          ) : descendants.length === 0 ? (
            <div className="text-sm text-muted-foreground">No descendant (resumed) jobs yet.</div>
          ) : (
            <div className="border rounded-md divide-y bg-muted/20 dark:divide-border/40">
              {descendants.map(d => (
                <div key={d.id} className="p-2 text-xs flex flex-wrap md:flex-nowrap items-center gap-2 hover:bg-background/60 cursor-pointer transition"
                  onClick={() => navigate(`/jobs/${d.id}`)}
                  title="View this descendant job"
                >
                  <span className="font-mono w-24 truncate">{shortId(d.id)}</span>
                  <div className="flex items-center gap-2">{statusBadge(d.status)}</div>
                  {d.resume_attempt && (
                    <Badge variant="outline" className="text-[10px] py-0 px-1">attempt {d.resume_attempt}</Badge>
                  )}
                  {d.children_count && d.children_count > 0 && (
                    <Badge variant="secondary" className="text-[10px] py-0 px-1">{d.children_count} child{d.children_count === 1 ? '' : 'ren'}</Badge>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    <button onClick={(e) => { e.stopPropagation(); copyId(d.id) }} className="opacity-40 hover:opacity-100 transition" title="Copy job ID">
                      <FaCopy className="size-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
