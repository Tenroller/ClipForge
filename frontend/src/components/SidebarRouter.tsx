import { useLocation, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'

type Props = {
  isCollapsed?: boolean
  onToggleCollapse?: () => void
  className?: string
  activeJobs?: number
}

export default function SidebarRouter({ isCollapsed, onToggleCollapse, className, activeJobs }: Props) {
  const location = useLocation()
  const navigate = useNavigate()

  const path = location.pathname
  const currentView: 'landing' | 'moneyprinter' | 'brainrot' | 'activity' | 'downloads' =
    path === '/' ? 'landing'
    : path.startsWith('/creator') ? 'moneyprinter'
    : path.startsWith('/compilations') ? 'brainrot'
    : path.startsWith('/activity') ? 'activity'
    : 'downloads'

  return (
    <Sidebar
      currentView={currentView}
      onNavigate={(view) => {
        if (view === 'landing') navigate('/')
        else if (view === 'moneyprinter') navigate('/creator')
        else if (view === 'brainrot') navigate('/compilations')
        else if (view === 'activity') navigate('/activity')
        else navigate('/downloads')
      }}
      isCollapsed={isCollapsed}
      onToggleCollapse={onToggleCollapse}
      activeJobs={activeJobs}
      className={className}
    />
  )
}


