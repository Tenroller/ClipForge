import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type Horizontal = 'left' | 'center' | 'right'
type Vertical = 'top' | 'center' | 'bottom'

export type SubtitlesPosition = `${Horizontal},${Vertical}`

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function snapToGrid(xPercent: number, yPercent: number): SubtitlesPosition {
  // Snap to 3x3 grid: 10%, 50%, 90%
  const candidates = [10, 50, 90]
  const closest = (v: number) => candidates.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a))
  const x = closest(xPercent)
  const y = closest(yPercent)

  const h: Horizontal = x <= 30 ? 'left' : x >= 70 ? 'right' : 'center'
  const v: Vertical = y <= 30 ? 'top' : y >= 70 ? 'bottom' : 'center'
  return `${h},${v}`
}

function positionToPercent(pos: SubtitlesPosition): { x: number; y: number } {
  const [h, v] = pos.split(',') as [Horizontal, Vertical]
  const x = h === 'left' ? 10 : h === 'right' ? 90 : 50
  const y = v === 'top' ? 15 : v === 'bottom' ? 85 : 50
  return { x, y }
}

function parsePosition(input: string | null | undefined, fallback: SubtitlesPosition): SubtitlesPosition {
  const value = String(input || '').trim().toLowerCase()
  const parts = value.split(',').map((p) => p.trim())
  const h = (parts[0] as Horizontal) || 'center'
  const v = (parts[1] as Vertical) || 'bottom'
  const isH: Record<string, boolean> = { left: true, center: true, right: true }
  const isV: Record<string, boolean> = { top: true, center: true, bottom: true }
  if (isH[h] && isV[v]) return `${h},${v}`
  return fallback
}

export function SubtitlePreview({
  color,
  position,
  onChangePosition,
  sampleText = 'This is how your subtitles will look',
  shadowLayer1Color = '#4A90E2',
  shadowLayer2Color = '#357ABD',
  shadowLayer3Color = '#2E5F8A',
  shadowLayer4Color = '#1E3F5A',
}: {
  color: string
  position: SubtitlesPosition
  onChangePosition: (pos: SubtitlesPosition) => void
  sampleText?: string
  shadowLayer1Color?: string
  shadowLayer2Color?: string
  shadowLayer3Color?: string
  shadowLayer4Color?: string
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const itemRef = useRef<HTMLDivElement | null>(null)
  const [{ dragging, startX, startY, originX, originY }, setDrag] = useState({
    dragging: false,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  })

  // Compute absolute position in px based on percentage
  const { xPx, yPx } = useMemo(() => {
    const container = containerRef.current
    const item = itemRef.current
    const { x, y } = positionToPercent(position)
    if (!container || !item) return { xPx: 0, yPx: 0 }
    const cw = container.clientWidth
    const ch = container.clientHeight
    const iw = item.clientWidth
    const ih = item.clientHeight
    const cx = (x / 100) * cw
    const cy = (y / 100) * ch
    return { xPx: clamp(cx - iw / 2, 0, cw - iw), yPx: clamp(cy - ih / 2, 0, ch - ih) }
  }, [position])

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
      const nx = clamp(originX + dx, 0, cw - iw)
      const ny = clamp(originY + dy, 0, ch - ih)
      const xCenter = (nx + iw / 2) / cw
      const yCenter = (ny + ih / 2) / ch
      const snapped = snapToGrid(xCenter * 100, yCenter * 100)
      onChangePosition(snapped)
    }
    function onUp() {
      if (dragging) setDrag((s) => ({ ...s, dragging: false }))
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [dragging, startX, startY, originX, originY, onChangePosition])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current || !itemRef.current) return
    const itemRect = itemRef.current.getBoundingClientRect()
    setDrag({ dragging: true, startX: e.clientX, startY: e.clientY, originX: itemRect.left - containerRef.current.getBoundingClientRect().left, originY: itemRect.top - containerRef.current.getBoundingClientRect().top })
  }, [])

  const setGrid = (h: Horizontal, v: Vertical) => onChangePosition(`${h},${v}`)

  // Create 3D blue shadow effect
  const textShadowStyle = `
    2px 2px 0px ${shadowLayer1Color},
    4px 4px 0px ${shadowLayer2Color},
    6px 6px 0px ${shadowLayer3Color},
    8px 8px 0px ${shadowLayer4Color}
  `

  return (
    <div className="space-y-3">
      <div
        ref={containerRef}
        className="relative w-full max-w-sm mx-auto rounded-lg overflow-hidden border border-zinc-800 bg-zinc-900 aspect-[9/16]"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-800/70 to-black/80" />
        <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-xs select-none">
          Video Preview
        </div>
        <div
          ref={itemRef}
          className="absolute cursor-move px-4 py-3 select-none"
          style={{ 
            left: xPx, 
            top: yPx, 
            color, 
            textShadow: textShadowStyle,
            letterSpacing: '1.5px',  // Generous letter spacing
            fontWeight: 'bold',      // Bold font
            fontSize: '14px'         // Slightly larger for better visibility
          }}
          onMouseDown={handleMouseDown}
        >
          <div className="text-center font-black leading-snug">
            {sampleText}
          </div>
        </div>
        <div className="absolute bottom-1 right-1 text-[10px] text-white/70 bg-black/30 px-1.5 py-0.5 rounded">
          {position}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1 max-w-sm mx-auto">
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('left', 'top')}>Left, Top</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('center', 'top')}>Center, Top</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('right', 'top')}>Right, Top</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('left', 'center')}>Left, Middle</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('center', 'center')}>Center, Middle</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('right', 'center')}>Right, Middle</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('left', 'bottom')}>Left, Bottom</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('center', 'bottom')}>Center, Bottom</button>
        <button type="button" className="h-8 rounded bg-zinc-800 hover:bg-zinc-700 text-xs" onClick={() => setGrid('right', 'bottom')}>Right, Bottom</button>
      </div>
    </div>
  )
}

// Helper exported for external parsing if users type manually
export const normalizeSubtitlesPosition = parsePosition


