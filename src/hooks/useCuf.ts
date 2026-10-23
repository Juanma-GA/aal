import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { materialsKey } from '@/hooks/useMaterials';
import { notifyError } from '@/lib/notify';
import { fetchCuf, putSubcategories } from '@/services/cufApi';
import type { Cuf } from '@/types/cuf';

export const cufKey = (materialId: string) => ['cuf', materialId] as const;

export function useCuf(materialId: string) {
  return useQuery({ queryKey: cufKey(materialId), queryFn: () => fetchCuf(materialId) });
}

/** The CUF's subcategories, all at once: the chips change at once and the
 *  figures come with the server's answer; a refusal undoes it (HR20; a 409
 *  of version offers to reload). */
export function useSetSubcategories(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const key = cufKey(materialId);
  return useMutation({
    mutationFn: ({ cuf, codes }: { cuf: Cuf; codes: string[]; added?: { code: string; name: string; category_code: string; category_name: string } }) =>
      putSubcategories(materialId, cuf.version, codes),
    onMutate: async ({ cuf, codes, added }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Cuf>(key);
      const kept = cuf.subcategories.filter((s) => codes.includes(s.code));
      const extra = added && !kept.some((s) => s.code === added.code) ? [{ ...added, sns_count: 0 }] : [];
      queryClient.setQueryData<Cuf>(key, { ...cuf, subcategories: [...kept, ...extra].sort((a, b) => a.code.localeCompare(b.code)) });
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
      notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: key }));
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(key, saved);
      void queryClient.invalidateQueries({ queryKey: ['cuf', materialId, 'tree'] });
      void queryClient.invalidateQueries({ queryKey: ['materials', materialId, 'activity'] });
      void queryClient.invalidateQueries({ queryKey: materialsKey });
    },
  });
}
