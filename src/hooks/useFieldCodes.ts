import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';
import { referenceValuesKey } from '@/hooks/useReferenceTables';
import { tableOf } from '@/lib/articleFields';
import { fetchReferenceValues } from '@/services/referenceApi';
import type { ArticleField, ReferenceValue } from '@/types/reference';

/** The values of every reference table the article fields use (and D114,
 *  the life controls'): table -> values, once loaded. */
export function useFieldCodes(fields: ArticleField[] | undefined): Record<string, ReferenceValue[]> {
  const tables = [...new Set([...(fields ?? []).map(tableOf).filter((t): t is string => Boolean(t)), 'D114'])].sort();
  const results = useQueries({ queries: tables.map((code) => ({ queryKey: referenceValuesKey(code), queryFn: () => fetchReferenceValues(code), enabled: Boolean(fields) })) });
  // The same object while no table changes: memoized children do not render again.
  const stamp = tables.map((code, i) => `${code}:${results[i]?.dataUpdatedAt ?? 0}`).join('|');
  return useMemo(() => {
    const out: Record<string, ReferenceValue[]> = {};
    tables.forEach((code, i) => {
      const data = results[i]?.data;
      if (data) out[code] = data;
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `stamp` says when the data changed
  }, [stamp]);
}

export const activeCodes = (values: ReferenceValue[] | undefined): Set<string> | undefined =>
  values ? new Set(values.filter((v) => v.is_active).map((v) => v.code)) : undefined;
