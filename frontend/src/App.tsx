import { useState } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Button } from '@/components/components/ui/button'
import { Clapperboard, Menu } from 'lucide-react'
import ThemeToggle from './components/ThemeToggle'
import CreatorPage from './pages/CreatorPage'
import CompilationsPage from './pages/CompilationsPage'
import ActivityPage from './pages/ActivityPage'
import DownloadsPage from './pages/DownloadsPage'
import NewLandingPage from './components/NewLandingPage'
import SidebarRouter from './components/SidebarRouter'
import AuthDialog from './components/AuthDialog'
import AuthStatus from './components/AuthStatus'
import { useJobManager } from './hooks/useJobManager'

const API = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8080'

export default function App() {
	const navigate = useNavigate()
	const location = useLocation()
	const [sidebarCollapsed, setSidebarCollapsed] = useState(true)
	const [showMobileSidebar, setShowMobileSidebar] = useState(false)
	const [showAuth, setShowAuth] = useState(false)
	
	// Get active job count for the sidebar
	const jobManager = useJobManager()
	const activeJobCount = jobManager.getActiveJobs().length

	const onGetStarted = () => {
		navigate('/creator')
	}

	// Check if we're on the landing page
	const isLandingPage = location.pathname === '/'

	// If on landing page, render it without sidebar/header
	if (isLandingPage) {
		return (
			<>
				<NewLandingPage onGetStarted={onGetStarted} />
				<AuthDialog open={showAuth} onOpenChange={setShowAuth} onAuth={() => window.location.reload()} />
			</>
		)
	}

	return (
		<div className="flex h-screen bg-background">
			{/* Sidebar */}
			<SidebarRouter
				isCollapsed={sidebarCollapsed}
				onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
				activeJobs={activeJobCount}
				className="hidden lg:flex"
			/>

			{/* Mobile Sidebar Overlay */}
			{showMobileSidebar && (
				<div className="lg:hidden fixed inset-0 z-50 bg-background/80 backdrop-blur-sm">
					<SidebarRouter
						isCollapsed={false}
						onToggleCollapse={() => setShowMobileSidebar(false)}
						activeJobs={activeJobCount}
						className="w-64"
					/>
				</div>
			)}

			{/* Main Content */}
			<div className="flex-1 flex flex-col overflow-hidden">
				{/* Header */}
				<header className="border-b border-border/30 bg-card/40 backdrop-blur-xl px-4 lg:px-6 py-3">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							{/* Mobile menu toggle */}
							<Button
								variant="ghost"
								size="sm"
								className="lg:hidden px-2"
								onClick={() => setShowMobileSidebar(!showMobileSidebar)}
							>
								<Menu className="size-4" />
							</Button>
							
							<div className="flex items-center gap-3">
								<div className="size-10 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center shadow-lg">
									<Clapperboard className="size-5 text-white" />
								</div>
								<div>
									<Routes>
										<Route path="/creator" element={
											<>
												<h1 className="section-title text-lg">AI Video Creator</h1>
												<p className="section-subtitle text-[11px]">Create videos with AI</p>
											</>
										} />
										<Route path="/compilations" element={
											<>
												<h1 className="section-title text-lg">Compilation Generator</h1>
												<p className="section-subtitle text-[11px]">Create from existing videos</p>
											</>
										} />
										<Route path="/activity" element={
											<>
												<h1 className="section-title text-lg">Recent Activity</h1>
												<p className="section-subtitle text-[11px]">View job history</p>
											</>
										} />
										<Route path="/downloads" element={
											<>
												<h1 className="section-title text-lg">Downloads</h1>
												<p className="section-subtitle text-[11px]">Download completed videos</p>
											</>
										} />
									</Routes>
								</div>
							</div>
						</div>
						
						<div className="flex items-center gap-3">
						<div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 border border-border/50">
								<div className="size-2 rounded-full bg-green-500 animate-pulse"></div>
								<span className="text-xs font-medium text-muted-foreground">API: {API.replace('http://', '')}</span>
							</div>
						<AuthStatus onLoginClick={() => setShowAuth(true)} />
						<ThemeToggle />
						</div>
					</div>
				</header>

				{/* Main Content Area */}
				<main className="flex-1 overflow-auto">
					<div className="container-page fade-in max-w-[1760px]">
						<div aria-live="polite" className="sr-only">App content</div>
						<Routes>
							<Route path="/creator" element={<CreatorPage />} />
							<Route path="/compilations" element={<CompilationsPage />} />
							<Route path="/activity" element={<ActivityPage />} />
							<Route path="/downloads" element={<DownloadsPage />} />
						</Routes>
					</div>
				</main>
				<AuthDialog open={showAuth} onOpenChange={setShowAuth} onAuth={() => window.location.reload()} />
			</div>
		</div>
	)
}


