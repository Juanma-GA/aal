import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import { updateUiPreferences } from '@/services/authApi';
import { useUiStore } from '@/stores/uiStore';
import type { Me } from '@/types/auth';
import { meKey, useMe } from './useSession';

/** The folded sidebar groups: in the UI store while the page lives, and in
 *  the user's ui_preferences on the server so a reload keeps them (HR1).
 *  A toggle shows at once and is saved in the background; if the server
 *  refuses it, it is undone (HR20). */
export function useSidebarGroups(): { collapsed: string[]; toggle: (code: string) => void } {
  const me = useMe();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const collapsed = useUiStore((s) => s.collapsedGroups);
  const setCollapsed = useUiStore((s) => s.setCollapsedGroups);
  const loadedFor = useRef<string | null>(null);

  // Once per user: the store starts from what the server has.
  useEffect(() => {
    if (me.data && loadedFor.current !== me.data.id) {
      loadedFor.current = me.data.id;
      setCollapsed(me.data.ui_preferences.sidebar_collapsed_groups ?? []);
    }
  }, [me.data, setCollapsed]);

  const toggle = (code: string) => {
    const previous = useUiStore.getState().collapsedGroups;
    const next = previous.includes(code) ? previous.filter((c) => c !== code) : [...previous, code];
    setCollapsed(next);
    updateUiPreferences({ sidebar_collapsed_groups: next })
      .then((saved) => queryClient.setQueryData<Me>(meKey, saved))
      .catch((error: unknown) => {
        setCollapsed(previous);
        notifyError(error, t);
      });
  };
  return { collapsed, toggle };
}
