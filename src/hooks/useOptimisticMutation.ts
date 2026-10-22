// HR20: a mutation shows its result at once on the cached list, persists in
// the background, and rolls the list back if the server refuses it (with a
// toast; a version conflict offers to reload).
import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';

interface Options<TItem, TVars, TResult> {
  queryKey: QueryKey;
  mutationFn: (vars: TVars) => Promise<TResult>;
  /** The list as it will be once the server agrees. */
  apply: (list: TItem[], vars: TVars) => TItem[];
  /** The list with the server's answer (its version, its dates). */
  settle?: (list: TItem[], result: TResult, vars: TVars) => TItem[];
  /** Other queries that depend on this change. */
  invalidate?: QueryKey[];
}

export function useOptimisticMutation<TItem, TVars, TResult>({ queryKey, mutationFn, apply, settle, invalidate = [] }: Options<TItem, TVars, TResult>) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn,
    onMutate: async (vars: TVars) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<TItem[]>(queryKey);
      if (previous) queryClient.setQueryData<TItem[]>(queryKey, apply(previous, vars));
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
      notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey }));
    },
    onSuccess: (result, vars) => {
      if (settle) {
        const current = queryClient.getQueryData<TItem[]>(queryKey);
        if (current) queryClient.setQueryData<TItem[]>(queryKey, settle(current, result, vars));
      }
      for (const key of invalidate) void queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
