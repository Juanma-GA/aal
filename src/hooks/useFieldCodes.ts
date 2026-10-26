import { useQueries } from '@tanstack/react-query';
import { referenceValuesKey } from '@/hooks/useReferenceTables';
import { tableOf } from '@/lib/articleFields';
import { fetchReferenceValues } from '@/services/referenceApi';
import type { ArticleField, ReferenceValue } from '@/types/reference';

/** The values of every reference table the article fields use (and D114,
 *  the life controls'): table -> values, once loaded. */
export function useFieldCodes(fields: ArticleField[] | undefined): Record<string, ReferenceValue[]> {
  const tables = [...new Set([...(fields ?? []).map(tableOf).filter((t): t is string => Boolean(t)), 'D114'])].sort();
  const results = useQueries({ queries: tables.map((code) => ({ queryKey: referenceValuesKey(code), queryFn: () => fetchReferenceValues(code), enabled: Boolean(fields) })) });
  const out: Record<string, ReferenceValue[]> = {};
  tables.forEach((code, i) => {
    const data = results[i]?.data;
    if (data) out[code] = data;
  });
  return out;
}

export const activeCodes = (values: ReferenceValue[] | undefined): Set<string> | undefined =>
  values ? new Set(values.filter((v) => v.is_active).map((v) => v.code)) : undefined;
