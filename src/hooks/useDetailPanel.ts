import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import { fetchUiSettings, updateUiPreferences } from '@/services/authApi';
import { useUiStore } from '@/stores/uiStore';
import type { Me } from '@/types/auth';
import { meKey, useMe } from './useSession';

/** From this width the detail panel is docked beside the content (E15);
 *  below, it is an overlay as before. */
export const DOCKED_QUERY = '(min-width: 1024px)';

function subscribe(onChange: () => void): () => void {
  const mql = window.matchMedia(DOCKED_QUERY);
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}

export function useDocked(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(DOCKED_QUERY).matches, () => false);
}

export interface DetailPanelWidth {
  width: number;
  limits: { min: number; max: number; default: number } | undefined;
  /** While dragging: only the screen; `save` keeps it in ui_preferences. */
  setWidth: (width: number, save: boolean) => void;
}

/** The docked panel's width (E15): the same for every detail panel, in the
 *  UI store while the page lives and in the user's ui_preferences on the
 *  server (HR1), like the sidebar's. A refused save is undone (HR20). */
export function useDetailPanelWidth(): DetailPanelWidth {
  const me = useMe();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ['ui-settings'], queryFn: fetchUiSettings, staleTime: Infinity, enabled: me.data !== undefined && !me.data.must_change_password });
  const limits = settings.data?.detail_panel_width;
  const live = useUiStore((s) => s.detailPanelWidth);
  const clamp = (value: number) => (limits ? Math.min(limits.max, Math.max(limits.min, Math.round(value))) : Math.round(value));
  const stored = me.data?.ui_preferences.detail_panel_width;
  const width = clamp(live ?? stored ?? limits?.default ?? 480);
  return {
    width,
    limits,
    setWidth: (next, keep) => {
      const value = clamp(next);
      useUiStore.getState().setDetailPanelWidth(value);
      if (!keep || value === stored) return;
      void updateUiPreferences({ detail_panel_width: value })
        .then((saved) => queryClient.setQueryData<Me>(meKey, saved))
        .catch((error: unknown) => {
          useUiStore.getState().setDetailPanelWidth(stored ?? limits?.default ?? value);
          notifyError(error, t);
        });
    },
  };
}
