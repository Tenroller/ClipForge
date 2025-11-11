import type React from "react"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

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
  // 3D Shadow colors for enhanced subtitles
  shadowLayersCount?: number
  shadowLayer1Color?: string
  shadowLayer2Color?: string
  shadowLayer3Color?: string
  shadowLayer4Color?: string
}

export default function PreviewPanel({ 
  position, 
  onChangePosition, 
  previewUrl, 
  color = "#FFFF00", 
  positionRaw, 
  onChangePositionRaw,
  shadowLayersCount = 4,
  shadowLayer1Color = '#4A90E2',
  shadowLayer2Color = '#357ABD',
  shadowLayer3Color = '#2E5F8A',
  shadowLayer4Color = '#1E3F5A'
}: PreviewPanelProps) {
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

    // If we have a raw position string, try to parse it
    if (positionRaw && positionRaw.startsWith('pct:')) {
      const [x, y] = positionRaw.replace('pct:', '').split(',').map(Number)
      if (!isNaN(x) && !isNaN(y)) {
        const cx = (x / 100) * cw
        const cy = (y / 100) * ch
        const left = Math.max(Math.min(cx - iw / 2, cw - iw), 0)
        const top = Math.max(Math.min(cy - ih / 2, ch - ih), 0)
        return { leftPx: left, topPx: top }
      }
    }

    // Default positioning based on position prop
    let cxPct = 50, cyPct = 85 // Default to center-bottom

    switch (position) {
      case "left-top":
        cxPct = 15; cyPct = 15
        break
      case "center-top":
        cxPct = 50; cyPct = 15
        break
      case "right-top":
        cxPct = 85; cyPct = 15
        break
      case "left-middle":
        cxPct = 15; cyPct = 50
        break
      case "center-middle":
        cxPct = 50; cyPct = 50
        break
      case "right-middle":
        cxPct = 85; cyPct = 50
        break
      case "left-bottom":
        cxPct = 15; cyPct = 85
        break
      case "center-bottom":
        cxPct = 50; cyPct = 85
        break
      case "right-bottom":
        cxPct = 85; cyPct = 85
        break
      default:
        cxPct = 50; cyPct = 85 // fallback to center-bottom
    }

    const cx = (cxPct / 100) * cw
    const cy = (cyPct / 100) * ch
    const left = Math.max(Math.min(cx - iw / 2, cw - iw), 0)
    const top = Math.max(Math.min(cy - ih / 2, ch - ih), 0)
    return { leftPx: left, topPx: top }
  }, [positionRaw, position, containerRef.current?.clientWidth, containerRef.current?.clientHeight])

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

  // Effect to recalculate position when container resizes or position changes
  useEffect(() => {
    const handleResize = () => {
      // Force re-calculation of position
      if (containerRef.current && itemRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        // Trigger re-render by updating a dummy state or just wait for next render
      }
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Effect to ensure initial position is set correctly
  useEffect(() => {
    if (containerRef.current && itemRef.current && !positionRaw?.startsWith('pct:')) {
      // Only update if we don't already have a custom position
      const timer = setTimeout(() => {
        if (containerRef.current && itemRef.current) {
          // Trigger position recalculation
          containerRef.current.dispatchEvent(new Event('resize'))
        }
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [position, positionRaw])

  // Create 3D blue shadow effect based on selected layer count
  const textShadowStyle = (() => {
    const allLayers = [
      `8px 8px 0px ${shadowLayer4Color}`,  // Furthest
      `6px 6px 0px ${shadowLayer3Color}`,
      `4px 4px 0px ${shadowLayer2Color}`,
      `2px 2px 0px ${shadowLayer1Color}`   // Closest
    ];
    
    // Select layers based on count (same logic as backend)
    if (shadowLayersCount === 2) {
      return [allLayers[0], allLayers[3]].join(', '); // Layer 4 and 1
    } else if (shadowLayersCount === 3) {
      return [allLayers[0], allLayers[1], allLayers[3]].join(', '); // Layer 4, 3, and 1
    } else { // 4 layers
      return allLayers.join(', ');
    }
  })()

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-base flex items-center gap-3">
          <div className="size-8 rounded-lg bg-gradient-to-br from-orange-500 to-pink-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">📱</span>
          </div>
          Preview
        </CardTitle>
        <Badge variant="outline" className="font-normal bg-muted/50">
          9:16
        </Badge>
      </CardHeader>
      <CardContent className="grid gap-4">
          <div ref={containerRef} className="relative mx-auto aspect-[9/16] w-full max-w-[300px] overflow-hidden rounded-xl border bg-gradient-to-b from-neutral-900 to-neutral-800 shadow-2xl" aria-label="Video preview area">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute inset-0 bg-[radial-gradient(transparent,rgba(0,0,0,0.35))]" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-white/60 space-y-2">
                <div className="size-12 mx-auto rounded-full bg-white/10 flex items-center justify-center">
                  <span className="text-2xl">🎬</span>
                </div>
                <p className="text-sm font-medium">Subtitle position preview</p>
              </div>
            </div>
          </div>

          {/* Draggable placement overlay (used for both grid and free modes) */}
          <div
            ref={itemRef}
            className="absolute px-3 py-2 select-none transition-all"
            style={{ 
              left: leftPx, 
              top: topPx, 
              color, 
              textShadow: textShadowStyle,
              letterSpacing: '1.5px',
              fontWeight: 'bold'
            }}
          >
            <div className="text-center font-black leading-snug">Example subtitle text</div>
          </div>

          <div className="absolute inset-x-2 bottom-2">
            <div className="text-right">
              <div className="inline-flex items-center px-2 py-1 rounded bg-black/60 backdrop-blur-sm border border-white/10">
                <span className="text-[10px] text-white/80 font-medium">
                  {positionRaw || position.replace("-", ", ")}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-xs font-medium text-muted-foreground mb-2">Subtitle Position</div>
          <div className="grid grid-cols-3 gap-2">
            {positions.slice(0, 3).map((p) => (
              <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
                {p.label}
              </PosChip>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {positions.slice(3, 6).map((p) => (
              <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
                {p.label}
              </PosChip>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {positions.slice(6, 9).map((p) => (
              <PosChip key={p.key} active={p.key === position} onClick={() => onChangePosition(p.key)}>
                {p.label}
              </PosChip>
            ))}
          </div>
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
      className={cn(
        "h-9 rounded-lg border text-xs font-medium transition-all duration-200",
        active 
          ? "bg-primary text-primary-foreground border-primary shadow-sm" 
          : "bg-background border-border hover:bg-muted/60 hover:border-border/70"
      )}
      aria-pressed={active}
    >
      {children}
    </button>
  )
}
