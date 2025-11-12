'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useActiveJobs } from '@/hooks/use-jobs';
import { ThemeToggle } from '@/components/theme-toggle';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import {
  Film,
  Brain,
  Images,
  TrendingUp,
  Trash2,
  ChevronRight,
  LogOut,
  Radio,
} from "lucide-react";
import { cn } from '@/lib/utils';
import { logoutAction } from '@/app/login/actions';
import { useTranslations } from 'next-intl';

type SidebarProps = {
  username: string;
  className?: string;
};

export default function Sidebar({ username, className }: SidebarProps) {
  const pathname = usePathname();
  const activeJobs = useActiveJobs();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const t = useTranslations('sidebar');

  // Filter active jobs by workflow type
  const moneyprinterJobs = activeJobs.filter(job => job.workflow === 'moneyprinter');
  const brainrotJobs = activeJobs.filter(job => job.workflow === 'brainrot');
  const podcastclipsJobs = activeJobs.filter(job => job.workflow === 'podcastclips');

  const navItems = [
    {
      id: 'creator',
      href: '/creator',
      label: t('navigation.creator.label'),
      icon: <Film className="size-4" />,
      description: t('navigation.creator.description'),
      badge: moneyprinterJobs.length > 0 ? moneyprinterJobs.length.toString() : undefined,
    },
    {
      id: 'compilations',
      href: '/compilations',
      label: t('navigation.compilations.label'),
      icon: <Brain className="size-4" />,
      description: t('navigation.compilations.description'),
      badge: brainrotJobs.length > 0 ? brainrotJobs.length.toString() : undefined,
    },
    {
      id: 'podcastclips',
      href: '/podcastclips',
      label: t('navigation.podcastClips.label'),
      icon: <Radio className="size-4" />,
      description: t('navigation.podcastClips.description'),
      badge: podcastclipsJobs.length > 0 ? podcastclipsJobs.length.toString() : undefined,
    },
  ];

  const utilityItems = [
    {
      id: 'videos',
      href: '/videos',
      label: t('navigation.videos.label'),
      icon: <Images className="size-4" />,
      description: t('navigation.videos.description'),
    },
    {
      id: 'activity',
      href: '/activity',
      label: t('navigation.activity.label'),
      icon: <TrendingUp className="size-4" />,
      description: t('navigation.activity.description'),
    },
    {
      id: 'cleanup',
      href: '/cleanup',
      label: t('navigation.cleanup.label'),
      icon: <Trash2 className="size-4" />,
      description: t('navigation.cleanup.description'),
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
            <h2 className="font-bold text-base">{t('appName')}</h2>
            <p className="text-xs text-muted-foreground">{t('welcomeMessage', { username })}</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-2 overflow-y-auto">
        <div className="space-y-1">
          <div className="px-2 py-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{t('sections.create')}</p>
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
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{t('sections.tools')}</p>
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
        {/* Theme Toggle */}
        <div className="flex items-center justify-between px-2">
          <span className="text-xs font-medium text-muted-foreground">{t('footer.theme')}</span>
          <ThemeToggle />
        </div>

        {/* Language Switcher */}
        <LanguageSwitcher />

        {/* Logout Button */}
        <form action={logoutAction}>
          <Button type="submit" variant="outline" className="w-full flex items-center gap-2 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/50">
            <LogOut className="size-4" />
            {t('footer.logout')}
          </Button>
        </form>

        {/* Status Indicator */}
        <div className="p-3 rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20 border-2 border-green-200/50 dark:border-green-800/30">
          <div className="flex items-center gap-2 mb-1">
            <div className="size-2 rounded-full bg-green-500 animate-pulse shadow-lg shadow-green-500/50" />
            <span className="text-xs font-semibold text-green-700 dark:text-green-400">{t('footer.apiStatus')}</span>
          </div>
          <div className="text-xs text-green-600 dark:text-green-500">{t('footer.connected')}</div>
        </div>
      </div>
    </aside>
  );
}
