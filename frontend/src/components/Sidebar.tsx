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
  LogOut,
  Radio,
  LayoutDashboard,
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
      badge: moneyprinterJobs.length > 0 ? moneyprinterJobs.length.toString() : undefined,
    },
    {
      id: 'compilations',
      href: '/compilations',
      label: t('navigation.compilations.label'),
      icon: <Brain className="size-4" />,
      badge: brainrotJobs.length > 0 ? brainrotJobs.length.toString() : undefined,
    },
    {
      id: 'podcastclips',
      href: '/podcastclips',
      label: t('navigation.podcastClips.label'),
      icon: <Radio className="size-4" />,
      badge: podcastclipsJobs.length > 0 ? podcastclipsJobs.length.toString() : undefined,
    },
  ];

  const utilityItems = [
    {
      id: 'videos',
      href: '/videos',
      label: t('navigation.videos.label'),
      icon: <Images className="size-4" />,
    },
    {
      id: 'activity',
      href: '/activity',
      label: t('navigation.activity.label'),
      icon: <TrendingUp className="size-4" />,
    },
    {
      id: 'cleanup',
      href: '/cleanup',
      label: t('navigation.cleanup.label'),
      icon: <Trash2 className="size-4" />,
    },
  ];

  return (
    <aside
      className={cn(
        'flex flex-col h-full bg-background border-r w-64 transition-all duration-300',
        className
      )}
    >
      {/* Header */}
      <div className="h-16 flex items-center px-6 border-b">
        <div className="flex items-center gap-2 font-semibold text-lg tracking-tight">
          <div className="size-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <LayoutDashboard className="size-5" />
          </div>
          <span>{t('appName')}</span>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-6 px-3 space-y-6">
        <div className="space-y-1">
          <h4 className="px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            {t('sections.create')}
          </h4>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link key={item.id} href={item.href} className="block">
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    className={cn(
                      'w-full justify-start gap-3 px-4 font-normal',
                      isActive && 'bg-secondary font-medium'
                    )}
                  >
                    {item.icon}
                    <span className="flex-1 text-left truncate">{item.label}</span>
                    {item.badge && (
                      <Badge variant="secondary" className="ml-auto h-5 px-1.5 min-w-5 flex items-center justify-center text-[10px]">
                        {item.badge}
                      </Badge>
                    )}
                  </Button>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="space-y-1">
          <h4 className="px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            {t('sections.tools')}
          </h4>
          <nav className="space-y-1">
            {utilityItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link key={item.id} href={item.href} className="block">
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    className={cn(
                      'w-full justify-start gap-3 px-4 font-normal',
                      isActive && 'bg-secondary font-medium'
                    )}
                  >
                    {item.icon}
                    <span className="flex-1 text-left truncate">{item.label}</span>
                  </Button>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t bg-muted/20 space-y-4">
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
              {username.charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-medium leading-none">{username}</span>
              <span className="text-xs text-muted-foreground">User</span>
            </div>
          </div>
          <ThemeToggle />
        </div>

        <div className="space-y-2">
          <LanguageSwitcher />
          <form action={logoutAction}>
            <Button type="submit" variant="outline" className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground">
              <LogOut className="size-4" />
              {t('footer.logout')}
            </Button>
          </form>
        </div>
      </div>
    </aside>
  );
}
