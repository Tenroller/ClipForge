'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
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
  FolderKanban,
} from "lucide-react";
import { logoutAction } from '@/app/login/actions';
import { useTranslations } from 'next-intl';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';

type AppSidebarProps = {
  username: string;
} & React.ComponentProps<typeof Sidebar>;

export default function AppSidebar({ username, ...props }: AppSidebarProps) {
  const pathname = usePathname();
  const activeJobs = useActiveJobs();
  const t = useTranslations('sidebar');
  const { state } = useSidebar();

  // Filter active jobs by workflow type
  const moneyprinterJobs = activeJobs.filter(job => job.workflow === 'moneyprinter');
  const brainrotJobs = activeJobs.filter(job => job.workflow === 'brainrot');
  const podcastclipsJobs = activeJobs.filter(job => job.workflow === 'podcastclips');

  const navItems = [
    {
      id: 'creator',
      href: '/creator',
      label: t('navigation.creator.label'),
      icon: Film,
      badge: moneyprinterJobs.length > 0 ? moneyprinterJobs.length.toString() : undefined,
    },
    {
      id: 'compilations',
      href: '/compilations',
      label: t('navigation.compilations.label'),
      icon: Brain,
      badge: brainrotJobs.length > 0 ? brainrotJobs.length.toString() : undefined,
    },
    {
      id: 'podcastclips',
      href: '/podcastclips',
      label: t('navigation.podcastClips.label'),
      icon: Radio,
      badge: podcastclipsJobs.length > 0 ? podcastclipsJobs.length.toString() : undefined,
    },
  ];

  const utilityItems = [
    {
      id: 'projects',
      href: '/projects',
      label: t('navigation.projects.label'),
      icon: FolderKanban,
    },
    {
      id: 'videos',
      href: '/videos',
      label: t('navigation.videos.label'),
      icon: Images,
    },
    {
      id: 'activity',
      href: '/activity',
      label: t('navigation.activity.label'),
      icon: TrendingUp,
    },
    {
      id: 'cleanup',
      href: '/cleanup',
      label: t('navigation.cleanup.label'),
      icon: Trash2,
    },
  ];

  return (
    <Sidebar collapsible="icon" {...props}>
      {/* Header */}
      <SidebarHeader>
        <div className="flex items-center gap-3 px-2 py-2 font-semibold text-lg tracking-tight">
          <img
            src="/logo.png"
            alt="ClipForge"
            className="size-10 rounded-lg object-contain"
          />
          <span className="group-data-[collapsible=icon]:hidden text-xl">{t('appName')}</span>
        </div>
      </SidebarHeader>

      {/* Navigation */}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t('sections.create')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={state === "collapsed" ? item.label : undefined}
                    >
                      <Link href={item.href}>
                        <item.icon className="size-4" />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                    {item.badge && (
                      <SidebarMenuBadge>
                        <span className="h-5 px-1.5 min-w-5 flex items-center justify-center text-[10px] text-muted-foreground">
                          {item.badge}
                        </span>
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>{t('sections.tools')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {utilityItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={state === "collapsed" ? item.label : undefined}
                    >
                      <Link href={item.href}>
                        <item.icon className="size-4" />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer */}
      <SidebarFooter>
        <div className="flex items-center justify-between px-2 group-data-[collapsible=icon]:justify-center">
          <div className="flex items-center gap-2 group-data-[collapsible=icon]:hidden">
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

        <div className="space-y-2 group-data-[collapsible=icon]:hidden">
          <LanguageSwitcher />
          <form action={logoutAction}>
            <Button type="submit" variant="outline" className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground">
              <LogOut className="size-4" />
              {t('footer.logout')}
            </Button>
          </form>
        </div>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
