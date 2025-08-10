import type React from "react"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/components/ui/card"
import { Badge } from "@/components/components/ui/badge"
import { cn } from "@/components/lib/utils"

type Position =
  | "left-top"
  | "center-top"
  | "right-top"
  | "left-middle"
  | "center-middle"
  | "right-middle"
  | "left-bottom"
  | "center-bottom"
  | "right-bottom"

const positions: { key: Position; label: string }[] = [
  { key: "left-top", label: "Left · Top" },
  { key: "center-top", label: "Center · Top" },
  { key: "right-top", label: "Right · Top" },
  { key: "left-middle", label: "Left · Middle" },
  { key: "center-middle", label: "Center · Middle" },
  { key: "right-middle", label: "Right · Middle" },
  { key: "left-bottom", label: "Left · Bottom" },
  { key: "center-bottom", label: "Center · Bottom" },
  { key: "right-bottom", label: "Right · Bottom" },
]

export type PreviewPanelProps = {
  position: Position
  onChangePosition: (pos: Position) => void
  previewUrl?: string | null
  // New: live subtitle color to preview
  color?: string
  // New: raw position string passed to backend. Supports:
  //   - "left,top" | "center,bottom" etc (existing)
  //   - "pct:x,y" (x,y are percentages of center anchor)
  //   - "px:x,y"  (absolute pixels for top-left of box)
  positionRaw?: string
  onChangePositionRaw?: (raw: string) => void
}

export default function PreviewPanel({ position, onChangePosition, previewUrl, color = "#FFFF00", positionRaw, onChangePositionRaw }: PreviewPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const itemRef = useRef<HTMLDivElement | null>(null)
  const [{ dragging, startX, startY, originX, originY }, setDrag] = useState({
    dragging: false,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  })

  const posClasses = useMemo(() => {
    const base = "absolute px-2 py-1 rounded-md bg-amber-400/90 text-black text-xs font-medium"
    switch (position) {
      case "left-top":
        return `${base} left-2 top-2`
      case "center-top":
        return `${base} left-1/2 -translate-x-1/2 top-2`
      case "right-top":
        return `${base} right-2 top-2`
      case "left-middle":
        return `${base} left-2 top-1/2 -translate-y-1/2`
      case "center-middle":
        return `${base} left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2`
      case "right-middle":
        return `${base} right-2 top-1/2 -translate-y-1/2`
      case "left-bottom":
        return `${base} left-2 bottom-2`
      case "center-bottom":
        return `${base} left-1/2 -translate-x-1/2 bottom-2`
      case "right-bottom":
        return `${base} right-2 bottom-2`
    }
  }, [position])

  // Compute absolute coordinates for draggable preview from raw value
  const { leftPx, topPx } = useMemo(() => {
    const container = containerRef.current
    const item = itemRef.current
    if (!container || !item) return { leftPx: 0, topPx: 0 }
    const cw = container.clientWidth
    const ch = container.clientHeight
    const iw = item.clientWidth
    const ih = item.clientHeight

    // Defaults map from grid position for initial placement
    const mapGridToCenterPercent = (p: Position): { x: number; y: number } => {
      const [h, v] = p.split("-") as ["left" | "center" | "right", "top" | "middle" | "bottom"]
      const x = h === "left" ? 10 : h === "right" ? 90 : 50
      const y = v === "top" ? 15 : v === "bottom" ? 85 : 50
      return { x, y }
    }

    const raw = String(positionRaw || "").trim().toLowerCase()
    let cxPct = 50, cyPct = 85
    if (raw.startsWith("pct:")) {
      const m = raw.match(/^pct:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)$/)
      if (m) { cxPct = Math.max(0, Math.min(100, parseFloat(m[1]))); cyPct = Math.max(0, Math.min(100, parseFloat(m[2]))) }
    } else if (raw.includes(",") && !raw.includes(":")) {
      // "left,top" style from legacy
      const grid = mapGridToCenterPercent(position)
      cxPct = grid.x
      cyPct = grid.y
    } else {
      const grid = mapGridToCenterPercent(position)
      cxPct = grid.x
      cyPct = grid.y
    }

    const cx = (cxPct / 100) * cw
    const cy = (cyPct / 100) * ch
    const left = Math.max(Math.min(cx - iw / 2, cw - iw), 0)
    const top = Math.max(Math.min(cy - ih / 2, ch - ih), 0)
    return { leftPx: left, topPx: top }
  }, [positionRaw, position])

  // Drag handling to produce pct:x,y value
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragging || !containerRef.current || !itemRef.current) return
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      const container = containerRef.current
      const item = itemRef.current
      const cw = container.clientWidth
      const ch = container.clientHeight
      const iw = item.clientWidth
      const ih = item.clientHeight
      const nx = Math.max(Math.min(originX + dx, cw - iw), 0)
      const ny = Math.max(Math.min(originY + dy, ch - ih), 0)
      const centerXPct = ((nx + iw / 2) / cw) * 100
      const centerYPct = ((ny + ih / 2) / ch) * 100
      onChangePositionRaw?.(`pct:${centerXPct.toFixed(1)},${centerYPct.toFixed(1)}`)
    }
    function onUp() { if (dragging) setDrag((s) => ({ ...s, dragging: false })) }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp) }
  }, [dragging, startX, startY, originX, originY, onChangePositionRaw])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current || !itemRef.current) return
    const itemRect = itemRef.current.getBoundingClientRect()
    const contRect = containerRef.current.getBoundingClientRect()
    setDrag({
      dragging: true,
      startX: e.clientX,
      startY: e.clientY,
      originX: itemRect.left - contRect.left,
      originY: itemRect.top - contRect.top,
    })
  }, [])

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-base">Preview</CardTitle>
        <Badge variant="outline" className="font-normal">
          9:16
        </Badge>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div ref={containerRef} className="relative mx-auto aspect-[9/16] w-full max-w-[340px] overflow-hidden rounded-xl border bg-gradient-to-b from-neutral-900 to-neutral-800" aria-label="Video preview area">
          {previewUrl ? (
            <video src={previewUrl} controls className="absolute inset-0 h-full w-full object-contain" />
          ) : (
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute inset-0 bg-[radial-gradient(transparent,rgba(0,0,0,0.35))]" />
            </div>
          )}

          {/* Draggable placement overlay (used for both grid and free modes) */}
          <div
            ref={itemRef}
            className="absolute cursor-move px-3 py-2 rounded-md bg-black/40 border border-white/10 select-none"
            style={{ left: leftPx, top: topPx, color, textShadow: '2px 2px 0px rgba(0,0,0,0.6), -2px -2px 0px rgba(0,0,0,0.6)' }}
            onMouseDown={handleMouseDown}
          >
            <div className="text-center font-semibold leading-snug">Example subtitle text</div>
          </div>

          <div className="absolute inset-x-2 bottom-2 text-[10px] text-muted-foreground">
            <div className="text-right">{positionRaw || position.replace("-", ", ")}</div>
          </div>
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-3 gap-2">
          {positions.slice(0, 3).map((p) => (
            <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
              {p.label}
            </PosChip>
          ))}
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-3 gap-2">
          {positions.slice(3, 6).map((p) => (
            <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
              {p.label}
            </PosChip>
          ))}
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-3 gap-2">
          {positions.slice(6, 9).map((p) => (
            <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
              {p.label}
            </PosChip>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function PosChip({
  active,
  onClick,
  children,
}: {
  active?: boolean
  onClick?: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn("h-9 rounded-md border text-xs", active ? "bg-muted" : "hover:bg-muted/60")}
      aria-pressed={active}
    >
      {children}
    </button>
  )
}
