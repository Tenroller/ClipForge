import { useState } from 'react'
import { Button } from '@/components/components/ui/button'
import { Badge } from '@/components/components/ui/badge'
import { Separator } from '@/components/components/ui/separator'
import {
  FaFilm,
  FaStar,
  FaBrain,
  FaHome,
  FaCog,
  FaQuestionCircle,
  FaBars,
  FaTimes,
  FaChartLine,
  FaDownload,
  FaHistory,
  FaChevronRight,
  FaTrash,
  FaImages
} from 'react-icons/fa'
import { cn } from '@/components/lib/utils'

type SidebarProps = {
  currentView: 'landing' | 'moneyprinter' | 'brainrot' | 'activity' | 'downloads' | 'cleanup' | 'videos'
  onNavigate: (view: 'landing' | 'moneyprinter' | 'brainrot' | 'activity' | 'downloads' | 'cleanup' | 'videos') => void
  onSettingsClick?: () => void
  className?: string
  isCollapsed?: boolean
  onToggleCollapse?: () => void
  activeJobs?: number
}

export default function Sidebar({ 
  currentView, 
  onNavigate, 
  onSettingsClick,
  className,
  isCollapsed = false,
  onToggleCollapse,
  activeJobs = 0
}: SidebarProps) {
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)

  const navItems = [
    {
      id: 'landing',
      label: 'Home',
      icon: <FaHome className="size-4" />,
      view: 'landing' as const,
      description: 'Landing page'
    },
    {
      id: 'moneyprinter',
      label: 'AI Video Creator',
      icon: <FaStar className="size-4" />,
      view: 'moneyprinter' as const,
      description: 'Create videos with AI',
      badge: activeJobs > 0 ? activeJobs.toString() : undefined
    },
    {
      id: 'brainrot',
      label: 'Compilations',
      icon: <FaBrain className="size-4" />,
      view: 'brainrot' as const,
      description: 'Create from existing videos'
    }
  ]

  const utilityItems = [
    {
      id: 'videos',
      label: 'Video Gallery',
      icon: <FaImages className="size-4" />,
      description: 'View all videos',
      disabled: false
    },
    {
      id: 'activity',
      label: 'Activity',
      icon: <FaChartLine className="size-4" />,
      description: 'Job history & status',
      disabled: false
    },
    {
      id: 'downloads',
      label: 'Downloads',
      icon: <FaDownload className="size-4" />,
      description: 'Manage your videos',
      disabled: false
    },
    {
      id: 'cleanup',
      label: 'Cleanup',
      icon: <FaTrash className="size-4" />,
      description: 'Clean temp files',
      disabled: false
    }
  ]

  return (
    <aside className={cn(
      "flex flex-col bg-card/40 backdrop-blur-xl border-r border-border/50 transition-all duration-300",
      isCollapsed ? "w-16" : "w-64",
      className
    )}>
      {/* Header */}
      <div className="p-4 border-b border-border/30">
        <div className="flex items-center justify-between">
          {!isCollapsed && (
            <div className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-gradient-to-br from-blue-500 via-purple-500 to-emerald-500 flex items-center justify-center shadow-lg">
                <FaFilm className="size-4 text-white" />
              </div>
              <div>
                <h2 className="font-semibold text-sm">AI Video Creator</h2>
                <p className="text-xs text-muted-foreground">Dashboard</p>
              </div>
            </div>
          )}
          {onToggleCollapse && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleCollapse}
              className="shrink-0 p-1.5 h-auto"
            >
              {isCollapsed ? <FaBars className="size-4" /> : <FaTimes className="size-4" />}
            </Button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-2">
        <div className="space-y-1">
          {!isCollapsed && (
            <div className="px-2 py-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Create
              </p>
            </div>
          )}
          
          {navItems.map((item) => (
            <Button
              key={item.id}
              variant={currentView === item.view ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start h-auto p-3 group relative",
                isCollapsed && "px-3 justify-center",
                currentView === item.view && "bg-primary/10 border border-primary/20 text-primary hover:bg-primary/15"
              )}
              onClick={() => onNavigate(item.view)}
              onMouseEnter={() => setHoveredItem(item.id)}
              onMouseLeave={() => setHoveredItem(null)}
            >
              <div className="flex items-center gap-3 w-full">
                <div className="shrink-0">
                  {item.icon}
                </div>
                {!isCollapsed && (
                  <>
                    <div className="flex-1 text-left">
                      <div className="font-medium text-sm">{item.label}</div>
                      <div className="text-xs text-muted-foreground">{item.description}</div>
                    </div>
                    {item.badge && (
                      <Badge variant="secondary" className="ml-auto">
                        {item.badge}
                      </Badge>
                    )}
                    {currentView === item.view && (
                      <FaChevronRight className="size-3 text-primary" />
                    )}
                  </>
                )}
              </div>

              {/* Tooltip for collapsed state */}
              {isCollapsed && hoveredItem === item.id && (
                <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 z-50 px-2 py-1 bg-popover border border-border rounded-md shadow-lg">
                  <div className="text-xs font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.description}</div>
                </div>
              )}
            </Button>
          ))}
        </div>

        <Separator className="my-4" />

        <div className="space-y-1">
          {!isCollapsed && (
            <div className="px-2 py-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Tools
              </p>
            </div>
          )}
          
          {utilityItems.map((item) => (
            <Button
              key={item.id}
              variant="ghost"
              className={cn(
                "w-full justify-start h-auto p-3 group relative",
                isCollapsed && "px-3 justify-center",
                item.disabled && "opacity-50 cursor-not-allowed"
              )}
              disabled={item.disabled}
              onClick={() => {
                if (item.id === 'videos') onNavigate('videos')
                if (item.id === 'activity') onNavigate('activity')
                if (item.id === 'downloads') onNavigate('downloads')
                if (item.id === 'cleanup') onNavigate('cleanup')
              }}
              onMouseEnter={() => setHoveredItem(item.id)}
              onMouseLeave={() => setHoveredItem(null)}
            >
              <div className="flex items-center gap-3 w-full">
                <div className="shrink-0">
                  {item.icon}
                </div>
                {!isCollapsed && (
                  <div className="flex-1 text-left">
                    <div className="font-medium text-sm">{item.label}</div>
                    <div className="text-xs text-muted-foreground">{item.description}</div>
                  </div>
                )}
              </div>

              {/* Tooltip for collapsed state */}
              {isCollapsed && hoveredItem === item.id && (
                <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 z-50 px-2 py-1 bg-popover border border-border rounded-md shadow-lg">
                  <div className="text-xs font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.description}</div>
                </div>
              )}
            </Button>
          ))}
        </div>
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border/30">
        <Button
          variant="ghost"
          className={cn(
            "w-full justify-start h-auto p-3 group",
            isCollapsed && "px-3 justify-center"
          )}
          onClick={onSettingsClick}
        >
          <div className="flex items-center gap-3 w-full">
            <FaCog className="size-4 shrink-0" />
            {!isCollapsed && (
              <div className="flex-1 text-left">
                <div className="font-medium text-sm">Settings</div>
                <div className="text-xs text-muted-foreground">Preferences</div>
              </div>
            )}
          </div>
        </Button>

        {!isCollapsed && (
          <div className="mt-3 p-2 rounded-lg bg-muted/30 border border-border/30">
            <div className="flex items-center gap-2 mb-1">
              <div className="size-2 rounded-full bg-green-500" />
              <span className="text-xs font-medium">API Status</span>
            </div>
            <div className="text-xs text-muted-foreground">Connected</div>
          </div>
        )}
      </div>
    </aside>
  )
}
