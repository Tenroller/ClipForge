'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useActiveJobs } from '@/hooks/use-jobs';
import {
  Film,
  Brain,
  Images,
  TrendingUp,
  Download,
  Trash2,
  ChevronRight,
  LogOut,
  Radio,
} from "lucide-react";
import { cn } from '@/lib/utils';
import { logoutAction } from '@/app/login/actions';

type SidebarProps = {
  username: string;
  className?: string;
};

export default function Sidebar({ username, className }: SidebarProps) {
  const pathname = usePathname();
  const activeJobs = useActiveJobs();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  // Filter active jobs by workflow type
  const moneyprinterJobs = activeJobs.filter(job => job.workflow === 'moneyprinter');
  const brainrotJobs = activeJobs.filter(job => job.workflow === 'brainrot');
  const podcastclipsJobs = activeJobs.filter(job => job.workflow === 'podcastclips');

  const navItems = [
    {
      id: 'creator',
      href: '/creator',
      label: 'AI Video Creator',
      icon: <Film className="size-4" />,
      description: 'Generate videos with AI',
      badge: moneyprinterJobs.length > 0 ? moneyprinterJobs.length.toString() : undefined,
    },
    {
      id: 'compilations',
      href: '/compilations',
      label: 'Compilations',
      icon: <Brain className="size-4" />,
      description: 'Create from existing videos',
      badge: brainrotJobs.length > 0 ? brainrotJobs.length.toString() : undefined,
    },
    {
      id: 'podcastclips',
      href: '/podcastclips',
      label: 'Podcast Clips',
      icon: <Radio className="size-4" />,
      description: 'Generate clips from podcasts',
      badge: podcastclipsJobs.length > 0 ? podcastclipsJobs.length.toString() : undefined,
    },
  ];

  const utilityItems = [
    {
      id: 'videos',
      href: '/videos',
      label: 'Video Gallery',
      icon: <Images className="size-4" />,
      description: 'View all videos',
    },
    {
      id: 'activity',
      href: '/activity',
      label: 'Activity',
      icon: <TrendingUp className="size-4" />,
      description: 'Job history & status',
    },
    {
      id: 'downloads',
      href: '/downloads',
      label: 'Downloads',
      icon: <Download className="size-4" />,
      description: 'Manage your videos',
    },
    {
      id: 'cleanup',
      href: '/cleanup',
      label: 'Cleanup',
      icon: <Trash2 className="size-4" />,
      description: 'Clean temp files',
    },
  ];

  return (
    <aside
      className={cn(
        'flex flex-col bg-card/80 backdrop-blur-2xl border-r-2 border-border/40 w-64 shadow-2xl overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <div className="p-5 border-b-2 border-border/30">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-xl bg-gradient-to-br from-primary via-accent to-secondary flex items-center justify-center shadow-xl shadow-primary/20">
            <Film className="size-5 text-white" />
          </div>
          <div>
            <h2 className="font-bold text-base">VideoHelper</h2>
            <p className="text-xs text-muted-foreground">Welcome, {username}</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-2 overflow-y-auto">
        <div className="space-y-1">
          <div className="px-2 py-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Create</p>
          </div>

          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link key={item.id} href={item.href}>
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  className={cn(
                    'w-full justify-start h-auto p-3 group relative rounded-xl transition-all duration-300 overflow-hidden',
                    isActive && 'bg-gradient-to-r from-primary/15 to-accent/15 border-2 border-primary/30 text-primary hover:from-primary/20 hover:to-accent/20 shadow-lg shadow-primary/10'
                  )}
                  onMouseEnter={() => setHoveredItem(item.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                >
                  <div className="flex items-center gap-3 w-full min-w-0">
                    <div className={cn(
                      "shrink-0 transition-transform duration-300",
                      isActive && "scale-110"
                    )}>{item.icon}</div>
                    <div className="flex-1 text-left min-w-0">
                      <div className="font-semibold text-sm truncate">{item.label}</div>
                      <div className="text-xs text-muted-foreground truncate">{item.description}</div>
                    </div>
                    {item.badge && (
                      <Badge variant="secondary" className="shrink-0">
                        {item.badge}
                      </Badge>
                    )}
                    {isActive && !item.badge && <ChevronRight className="size-3 text-primary animate-pulse shrink-0" />}
                  </div>
                </Button>
              </Link>
            );
          })}
        </div>

        <Separator className="my-4" />

        <div className="space-y-1">
          <div className="px-2 py-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Tools</p>
          </div>

          {utilityItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link key={item.id} href={item.href}>
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  className={cn(
                    'w-full justify-start h-auto p-3 group relative rounded-xl transition-all duration-300 overflow-hidden',
                    isActive && 'bg-gradient-to-r from-primary/15 to-accent/15 border-2 border-primary/30 text-primary hover:from-primary/20 hover:to-accent/20 shadow-lg shadow-primary/10'
                  )}
                  onMouseEnter={() => setHoveredItem(item.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                >
                  <div className="flex items-center gap-3 w-full min-w-0">
                    <div className={cn(
                      "shrink-0 transition-transform duration-300",
                      isActive && "scale-110"
                    )}>{item.icon}</div>
                    <div className="flex-1 text-left min-w-0">
                      <div className="font-semibold text-sm truncate">{item.label}</div>
                      <div className="text-xs text-muted-foreground truncate">{item.description}</div>
                    </div>
                    {isActive && <ChevronRight className="size-3 text-primary animate-pulse shrink-0" />}
                  </div>
                </Button>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t-2 border-border/30 space-y-3">
        {/* Logout Button */}
        <form action={logoutAction}>
          <Button type="submit" variant="outline" className="w-full flex items-center gap-2 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/50">
            <LogOut className="size-4" />
            Logout
          </Button>
        </form>

        {/* Status Indicator */}
        <div className="p-3 rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20 border-2 border-green-200/50 dark:border-green-800/30">
          <div className="flex items-center gap-2 mb-1">
            <div className="size-2 rounded-full bg-green-500 animate-pulse shadow-lg shadow-green-500/50" />
            <span className="text-xs font-semibold text-green-700 dark:text-green-400">API Status</span>
          </div>
          <div className="text-xs text-green-600 dark:text-green-500">Connected</div>
        </div>
      </div>
    </aside>
  );
}
