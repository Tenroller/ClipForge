import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/components/ui/dialog'
import { Button } from '@/components/components/ui/button'
import { Input } from '@/components/components/ui/input'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function AuthDialog({ open, onOpenChange, onAuth }: { open: boolean; onOpenChange: (v: boolean) => void; onAuth?: () => void }) {
	const [mode, setMode] = useState<'login' | 'register'>('login')
	const [email, setEmail] = useState('')
	const [password, setPassword] = useState('')
	const [busy, setBusy] = useState(false)
	const [error, setError] = useState<string | null>(null)

	async function submit(e: React.FormEvent) {
		e.preventDefault()
		setBusy(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE}/api/auth/${mode}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({ email, password }),
			})
			if (!res.ok) {
				const j = await res.json().catch(() => ({}))
				throw new Error(j?.detail || 'Request failed')
			}
			onAuth?.()
			onOpenChange(false)
		} catch (e: any) {
			setError(e.message || 'Failed')
		} finally {
			setBusy(false)
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{mode === 'login' ? 'Login' : 'Register'}</DialogTitle>
				</DialogHeader>
				<form onSubmit={submit} className="grid gap-3">
					<Input type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
					<Input type="password" placeholder="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
					{error ? <div className="text-xs text-red-600">{error}</div> : null}
					<div className="flex items-center justify-between gap-2">
						<Button type="submit" disabled={busy} className="btn-primary">
							{busy ? 'Please wait…' : mode === 'login' ? 'Login' : 'Create account'}
						</Button>
						<Button type="button" variant="ghost" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
							{mode === 'login' ? 'Need an account?' : 'Have an account?'}
						</Button>
					</div>
				</form>
			</DialogContent>
		</Dialog>
	)
}

