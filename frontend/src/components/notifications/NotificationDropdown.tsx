'use client';

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import {
  Bell,
  CheckCircle2,
  XCircle,
  Info,
  CheckCheck,
  Trash2,
} from 'lucide-react';
import { useNotifications, type AppNotification } from '@/hooks/useNotifications';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/components/ui/sidebar';
import { useState } from 'react';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getNotificationIcon(type: AppNotification['type']) {
  switch (type) {
    case 'success':
      return <CheckCircle2 className="size-4 shrink-0 text-success" />;
    case 'error':
      return <XCircle className="size-4 shrink-0 text-destructive" />;
    case 'info':
    default:
      return <Info className="size-4 shrink-0 text-info" />;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatRelativeTime(timestamp: number, t: any) {
  const diff = Date.now() - timestamp;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return t('timeAgo.justNow');
  if (minutes < 60) return t('timeAgo.minutesAgo', { count: minutes });
  if (hours < 24) return t('timeAgo.hoursAgo', { count: hours });
  return t('timeAgo.daysAgo', { count: days });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NotificationDropdown() {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    clearAll,
  } = useNotifications();

  const t = useTranslations('notifications');
  const router = useRouter();
  const { state: sidebarState } = useSidebar();
  const [open, setOpen] = useState(false);

  function handleNotificationClick(notification: AppNotification) {
    if (!notification.read) {
      markAsRead(notification.id);
    }
    if (notification.jobId) {
      router.push(`/job/${notification.jobId}`);
      setOpen(false);
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          'relative inline-flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors',
          sidebarState === 'collapsed' && 'hidden'
        )}
        aria-label={t('title')}
      >
        <Bell className="size-4" />
        {unreadCount > 0 && (
          <Badge
            variant="destructive"
            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] leading-none"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </Badge>
        )}
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={8}
        className="w-80 p-0"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h4 className="text-sm font-semibold">{t('title')}</h4>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 px-2 text-xs"
                onClick={() => markAllAsRead()}
              >
                <CheckCheck className="size-3" />
                {t('markAllRead')}
              </Button>
            )}
            {notifications.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 px-2 text-xs text-muted-foreground"
                onClick={() => clearAll()}
              >
                <Trash2 className="size-3" />
                {t('clearAll')}
              </Button>
            )}
          </div>
        </div>

        {/* Notification list */}
        <ScrollArea className="max-h-80">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Bell className="size-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">{t('empty')}</p>
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  className={cn(
                    'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/50',
                    !notification.read && 'bg-accent/30'
                  )}
                  onClick={() => handleNotificationClick(notification)}
                >
                  <div className="mt-0.5">
                    {getNotificationIcon(notification.type)}
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p
                        className={cn(
                          'text-sm truncate',
                          !notification.read ? 'font-semibold' : 'font-medium'
                        )}
                      >
                        {notification.title}
                      </p>
                      {!notification.read && (
                        <div className="size-2 shrink-0 rounded-full bg-primary" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {notification.description}
                    </p>
                    <p className="text-[11px] text-muted-foreground/70">
                      {formatRelativeTime(notification.timestamp, t)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
