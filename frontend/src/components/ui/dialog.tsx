import { ReactNode } from 'react'

export function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange?: (v: boolean) => void; children: ReactNode }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={() => onOpenChange?.(false)} />
      <div className="relative z-10 w-full max-w-md mx-4">{children}</div>
    </div>
  )
}

export function DialogContent({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card text-card-foreground shadow-lg p-4">
      {children}
    </div>
  )
}

export function DialogHeader({ children }: { children: ReactNode }) {
  return <div className="mb-3">{children}</div>
}

export function DialogTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-base font-semibold">{children}</h3>
}



