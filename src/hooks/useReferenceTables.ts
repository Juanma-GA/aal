import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { fetchArticleFields, fetchReferenceTable, fetchReferenceTables, fetchReferenceValues, updateReferenceValue } from '@/services/referenceApi';
import type { ReferenceValue, ReferenceValueUpdate } from '@/types/reference';

export const referenceTablesKey = ['reference-tables'] as const;
export const referenceTableKey = (code: string) => ['reference-tables', code] as const;
export const referenceValuesKey = (code: string) => ['reference-tables', code, 'values'] as const;

export function useReferenceTables() {
  return useQuery({ queryKey: referenceTablesKey, queryFn: fetchReferenceTables });
}

export function useReferenceTable(code: string) {
  return useQuery({ queryKey: referenceTableKey(code), queryFn: () => fetchReferenceTable(code) });
}

export function useReferenceValues(code: string) {
  return useQuery({ queryKey: referenceValuesKey(code), queryFn: () => fetchReferenceValues(code) });
}

export function useArticleFields() {
  return useQuery({ queryKey: ['article-fields'], queryFn: fetchArticleFields });
}

/** Everything that shows a table's values or counts, after a change. */
export function useRefreshReferenceTable(code: string): () => void {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: referenceTableKey(code) }).then(() => queryClient.invalidateQueries({ queryKey: referenceTablesKey, exact: true }));
}

interface UpdateVars {
  value: ReferenceValue;
  changes: Omit<ReferenceValueUpdate, 'version'>;
}

/** Edit, activate or deactivate a value: shown at once, saved in the
 *  background, undone if the server refuses it (HR20; a 409 offers to
 *  reload). */
export function useUpdateReferenceValue(code: string) {
  return useOptimisticMutation<ReferenceValue, UpdateVars, ReferenceValue>({
    queryKey: referenceValuesKey(code),
    mutationFn: ({ value, changes }) => updateReferenceValue(code, value.id, { version: value.version, ...changes }),
    apply: (list, { value, changes }) => list.map((v) => (v.id === value.id ? { ...v, ...changes } : v)),
    settle: (list, saved) => list.map((v) => (v.id === saved.id ? saved : v)),
    invalidate: [referenceTablesKey, referenceTableKey(code)],
  });
}
