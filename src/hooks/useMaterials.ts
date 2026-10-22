import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMaterials } from '@/services/adminApi';
import { updateUiPreferences } from '@/services/authApi';
import { useAuthStore } from '@/stores/authStore';
import type { Material, Me } from '@/types/auth';
import { meKey, useMe } from './useSession';

export const materialsKey = ['materials'] as const;

/** The materials the user is assigned to (an admin: all), each with their
 *  role and permissions on it. */
export function useMaterials() {
  const status = useAuthStore((s) => s.status);
  const me = useMe();
  return useQuery<Material[]>({
    queryKey: materialsKey,
    queryFn: fetchMaterials,
    enabled: status === 'signedIn' && me.data !== undefined && !me.data.must_change_password,
  });
}

/** The active material: the one in the user's server-side preferences
 *  (HR1), if they still have access to it. */
export function useActiveMaterial(): Material | null {
  const me = useMe();
  const materials = useMaterials();
  const id = me.data?.ui_preferences.active_material_id;
  return materials.data?.find((m) => m.id === id) ?? null;
}

/** Whether the user may `permission` on the active material. Buttons and
 *  actions read it; the server checks it again on every call. */
export function useMaterialPermission(permission: string): boolean {
  return useActiveMaterial()?.permissions.includes(permission) ?? false;
}

/** Changes the active material: optimistic (HR20), rolled back if the
 *  server refuses it. */
export function useSetActiveMaterial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (materialId: string | null) => updateUiPreferences({ active_material_id: materialId }),
    onMutate: async (materialId) => {
      await queryClient.cancelQueries({ queryKey: meKey });
      const previous = queryClient.getQueryData<Me>(meKey);
      if (previous) {
        queryClient.setQueryData<Me>(meKey, {
          ...previous,
          ui_preferences: { ...previous.ui_preferences, active_material_id: materialId },
        });
      }
      return { previous };
    },
    onError: (_error, _id, context) => {
      if (context?.previous) queryClient.setQueryData(meKey, context.previous);
    },
    onSuccess: (me) => queryClient.setQueryData(meKey, me),
  });
}
