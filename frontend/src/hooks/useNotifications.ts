'use client';

import { useEffect, useSyncExternalStore } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type NotificationType = 'success' | 'error' | 'info';

export interface AppNotification {
  id: string;
  title: string;
  description: string;
  type: NotificationType;
  timestamp: number;
  read: boolean;
  jobId?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'clipforge_notifications';
const MAX_NOTIFICATIONS = 50;

// ---------------------------------------------------------------------------
// In-memory store (singleton, shared across all hook consumers)
// ---------------------------------------------------------------------------

let notifications: AppNotification[] = [];
const listeners = new Set<() => void>();

function emitChange() {
  listeners.forEach((listener) => listener());
}

function loadFromStorage(): AppNotification[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AppNotification[]) : [];
  } catch {
    return [];
  }
}

function persist(items: AppNotification[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Storage full or unavailable – silently ignore
  }
}

function initStore() {
  notifications = loadFromStorage();
}

// Initialise once on module load (client only)
if (typeof window !== 'undefined') {
  initStore();
}

// ---------------------------------------------------------------------------
// Store actions
// ---------------------------------------------------------------------------

let idCounter = Date.now();

function generateId(): string {
  return `notif_${++idCounter}`;
}

export function addNotification(
  notification: Omit<AppNotification, 'id' | 'timestamp' | 'read'>,
) {
  const newNotification: AppNotification = {
    ...notification,
    id: generateId(),
    timestamp: Date.now(),
    read: false,
  };

  notifications = [newNotification, ...notifications].slice(0, MAX_NOTIFICATIONS);
  persist(notifications);
  emitChange();

  return newNotification;
}

export function markAsRead(id: string) {
  notifications = notifications.map((n) =>
    n.id === id ? { ...n, read: true } : n,
  );
  persist(notifications);
  emitChange();
}

export function markAllAsRead() {
  notifications = notifications.map((n) => ({ ...n, read: true }));
  persist(notifications);
  emitChange();
}

export function clearAll() {
  notifications = [];
  persist(notifications);
  emitChange();
}

export function removeNotification(id: string) {
  notifications = notifications.filter((n) => n.id !== id);
  persist(notifications);
  emitChange();
}

// ---------------------------------------------------------------------------
// Hook (useSyncExternalStore for tear-free reads)
// ---------------------------------------------------------------------------

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

function getSnapshot() {
  return notifications;
}

function getServerSnapshot(): AppNotification[] {
  return [];
}

export function useNotifications() {
  const items = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // Re-sync from localStorage when the tab regains focus (multi-tab support)
  useEffect(() => {
    function handleFocus() {
      const stored = loadFromStorage();
      if (JSON.stringify(stored) !== JSON.stringify(notifications)) {
        notifications = stored;
        emitChange();
      }
    }
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  const unreadCount = items.filter((n) => !n.read).length;

  return {
    notifications: items,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    clearAll,
    removeNotification,
  };
}
