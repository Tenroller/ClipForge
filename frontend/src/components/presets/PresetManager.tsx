'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Save, Trash2, Pencil, BookmarkPlus, Bookmark } from 'lucide-react';
import type { Preset, PresetConfig } from '@/hooks/usePresets';

export type PresetManagerProps = {
  presets: Preset[];
  onSave: (name: string, config: PresetConfig) => void;
  onLoad: (config: PresetConfig) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, newName: string) => void;
  getCurrentConfig: () => PresetConfig;
};

export default function PresetManager({
  presets,
  onSave,
  onLoad,
  onDelete,
  onRename,
  getCurrentConfig,
}: PresetManagerProps) {
  const t = useTranslations('presets');

  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [presetName, setPresetName] = useState('');
  const [targetPreset, setTargetPreset] = useState<Preset | null>(null);

  const handleSave = () => {
    const trimmed = presetName.trim();
    if (!trimmed) return;
    onSave(trimmed, getCurrentConfig());
    setPresetName('');
    setSaveDialogOpen(false);
  };

  const handleRename = () => {
    const trimmed = presetName.trim();
    if (!trimmed || !targetPreset) return;
    onRename(targetPreset.id, trimmed);
    setPresetName('');
    setTargetPreset(null);
    setRenameDialogOpen(false);
  };

  const handleDelete = () => {
    if (!targetPreset) return;
    onDelete(targetPreset.id);
    setTargetPreset(null);
    setDeleteDialogOpen(false);
  };

  const openRenameDialog = (preset: Preset) => {
    setTargetPreset(preset);
    setPresetName(preset.name);
    setRenameDialogOpen(true);
  };

  const openDeleteDialog = (preset: Preset) => {
    setTargetPreset(preset);
    setDeleteDialogOpen(true);
  };

  const formatDate = (ts: number) => {
    return new Date(ts).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Bookmark className="size-4" />
            {t('presets')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          {/* Save new preset */}
          <DropdownMenuItem
            onSelect={() => {
              setPresetName('');
              setSaveDialogOpen(true);
            }}
            className="gap-2 font-medium"
          >
            <BookmarkPlus className="size-4" />
            {t('saveCurrentSettings')}
          </DropdownMenuItem>

          {presets.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>{t('savedPresets')}</DropdownMenuLabel>

              {presets.map((preset) => (
                <DropdownMenuItem
                  key={preset.id}
                  className="flex items-center justify-between gap-2 pr-1"
                  onSelect={(e) => {
                    e.preventDefault();
                  }}
                >
                  <button
                    className="flex flex-col items-start gap-0.5 flex-1 min-w-0 text-left"
                    onClick={() => {
                      onLoad(preset.config);
                    }}
                  >
                    <span className="text-sm font-medium truncate w-full">
                      {preset.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {formatDate(preset.createdAt)}
                    </span>
                  </button>
                  <div className="flex items-center gap-0.5 flex-shrink-0">
                    <button
                      className="p-1 rounded-sm hover:bg-muted transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        openRenameDialog(preset);
                      }}
                      title={t('rename')}
                    >
                      <Pencil className="size-3 text-muted-foreground" />
                    </button>
                    <button
                      className="p-1 rounded-sm hover:bg-destructive/10 transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        openDeleteDialog(preset);
                      }}
                      title={t('delete')}
                    >
                      <Trash2 className="size-3 text-destructive" />
                    </button>
                  </div>
                </DropdownMenuItem>
              ))}
            </>
          )}

          {presets.length === 0 && (
            <>
              <DropdownMenuSeparator />
              <div className="px-2 py-3 text-center text-xs text-muted-foreground">
                {t('noPresets')}
              </div>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Save Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('savePreset')}</DialogTitle>
            <DialogDescription>{t('savePresetDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Input
              placeholder={t('presetNamePlaceholder')}
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSave();
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleSave} disabled={!presetName.trim()}>
              <Save className="size-4 mr-2" />
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('renamePreset')}</DialogTitle>
            <DialogDescription>{t('renamePresetDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Input
              placeholder={t('presetNamePlaceholder')}
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameDialogOpen(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleRename} disabled={!presetName.trim()}>
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('deletePreset')}</DialogTitle>
            <DialogDescription>
              {t('deletePresetDescription', { name: targetPreset?.name ?? '' })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              <Trash2 className="size-4 mr-2" />
              {t('delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
