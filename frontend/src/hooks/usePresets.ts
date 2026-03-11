'use client';

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'clipforge-presets';

export interface PresetConfig {
  // Core settings
  aiModel: string;
  voice: string;
  subtitleColor: string;
  subtitlesPosition: string;
  position: string;
  positionRaw: string;

  // Shadow layers
  shadowLayersCount: number;
  shadowLayer1Color: string;
  shadowLayer2Color: string;
  shadowLayer3Color: string;
  shadowLayer4Color: string;
}

export interface Preset {
  id: string;
  name: string;
  workflow: string;
  createdAt: number;
  config: PresetConfig;
}

function generateId(): string {
  return `preset_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

function loadPresetsFromStorage(): Preset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function savePresetsToStorage(presets: Preset[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

export function usePresets() {
  const [presets, setPresets] = useState<Preset[]>([]);

  // Hydrate from localStorage on mount
  useEffect(() => {
    setPresets(loadPresetsFromStorage());
  }, []);

  const savePreset = useCallback((name: string, config: PresetConfig): Preset => {
    const preset: Preset = {
      id: generateId(),
      name,
      workflow: 'moneyprinter',
      createdAt: Date.now(),
      config,
    };
    setPresets((prev) => {
      const next = [preset, ...prev];
      savePresetsToStorage(next);
      return next;
    });
    return preset;
  }, []);

  const loadPreset = useCallback((id: string): PresetConfig | null => {
    const all = loadPresetsFromStorage();
    const found = all.find((p) => p.id === id);
    return found?.config ?? null;
  }, []);

  const deletePreset = useCallback((id: string): void => {
    setPresets((prev) => {
      const next = prev.filter((p) => p.id !== id);
      savePresetsToStorage(next);
      return next;
    });
  }, []);

  const renamePreset = useCallback((id: string, newName: string): void => {
    setPresets((prev) => {
      const next = prev.map((p) =>
        p.id === id ? { ...p, name: newName } : p,
      );
      savePresetsToStorage(next);
      return next;
    });
  }, []);

  return {
    presets,
    savePreset,
    loadPreset,
    deletePreset,
    renamePreset,
  };
}
