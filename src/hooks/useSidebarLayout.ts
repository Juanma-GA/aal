import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import { fetchUiSettings, updateUiPreferences } from '@/services/authApi';
import { useUiStore } from '@/stores/uiStore';
import type { Me, SidebarSide, UiPreferences } from '@/types/auth';
import { meKey, useMe } from './useSession';

export interface SidebarLayout {
  open: boolean;
  width: number;
  side: SidebarSide;
  limits: { min: number; max: number; default: number } | undefined;
  setOpen: (open: boolean) => void;
  /** While dragging: only the screen; `save` keeps it. */
  setWidth: (width: number, save: boolean) => void;
  setSide: (side: SidebarSide) => void;
}

/** The sidebar's layout (E12): folded to its icons or not, its width and
 *  its side. In the UI store while the page lives and in the user's
 *  ui_preferences on the server, so it is the same after a reload or a new
 *  login (HR1). A change shows at once and is saved in the background; if
 *  the server refuses it, it is undone (HR20). */
export function useSidebarLayout(): SidebarLayout {
  const me = useMe();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  // Only once in: before the password change the API answers 403.
  const settings = useQuery({
    queryKey: ['ui-settings'],
    queryFn: fetchUiSettings,
    staleTime: Infinity,
    enabled: me.data !== undefined && !me.data.must_change_password,
  });
  const limits = settings.data?.sidebar_width;
  const open = useUiStore((s) => s.sidebarOpen);
  const width = useUiStore((s) => s.sidebarWidth);
  const side = useUiStore((s) => s.sidebarSide);
  const loadedFor = useRef<string | null>(null);

  // Once per user: the store starts from what the server has.
  useEffect(() => {
    if (me.data && limits && loadedFor.current !== me.data.id) {
      loadedFor.current = me.data.id;
      const prefs = me.data.ui_preferences;
      const store = useUiStore.getState();
      store.setSidebarOpen(!prefs.sidebar_folded);
      store.setSidebarWidth(Math.min(limits.max, Math.max(limits.min, prefs.sidebar_width ?? limits.default)));
      store.setSidebarSide(prefs.sidebar_side ?? 'left');
    }
  }, [me.data, limits]);

  const save = (patch: UiPreferences, undo: () => void) =>
    updateUiPreferences(patch)
      .then((saved) => queryClient.setQueryData<Me>(meKey, saved))
      .catch((error: unknown) => {
        undo();
        notifyError(error, t);
      });

  const clamp = (value: number) => (limits ? Math.min(limits.max, Math.max(limits.min, Math.round(value))) : Math.round(value));
  return {
    open,
    width: width ?? limits?.default ?? 256,
    side,
    limits,
    setOpen: (next) => {
      const previous = useUiStore.getState().sidebarOpen;
      useUiStore.getState().setSidebarOpen(next);
      if (next !== previous) void save({ sidebar_folded: !next }, () => useUiStore.getState().setSidebarOpen(previous));
    },
    setWidth: (next, keep) => {
      const value = clamp(next);
      useUiStore.getState().setSidebarWidth(value);
      const stored = me.data?.ui_preferences.sidebar_width;
      if (keep && value !== stored) void save({ sidebar_width: value }, () => useUiStore.getState().setSidebarWidth(stored ?? limits?.default ?? value));
    },
    setSide: (next) => {
      const previous = useUiStore.getState().sidebarSide;
      useUiStore.getState().setSidebarSide(next);
      void save({ sidebar_side: next }, () => useUiStore.getState().setSidebarSide(previous));
    },
  };
}
