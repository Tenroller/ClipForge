import { useEffect, useState } from 'react'
import { Button } from '@/components/components/ui/button'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function AuthStatus({ onLoginClick }: { onLoginClick: () => void }) {
  const [loading, setLoading] = useState(true)
  const [auth, setAuth] = useState<{ authenticated: boolean; email?: string } | null>(null)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' })
        const j = await res.json()
        setAuth(j)
      } catch {
        setAuth({ authenticated: false })
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  async function logout() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', credentials: 'include' })
    } catch {}
    window.location.reload()
  }

  if (loading) return null
  if (!auth?.authenticated) return <Button size="sm" variant="secondary" onClick={onLoginClick}>Login</Button>
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">{auth.email || 'Logged in'}</span>
      <Button size="sm" variant="outline" onClick={logout}>Logout</Button>
    </div>
  )
}



