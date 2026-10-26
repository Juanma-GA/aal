import { type QueryClient, type QueryKey, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import {
  addAlternativeCs,
  createRow,
  deleteRow,
  duplicateAlternative,
  fetchRow,
  fetchRows,
  fetchSummary,
  resetAl,
  updateRow,
} from '@/services/confunfisApi';
import type { PositionRow, RowDetail, RowFilters, RowPage, RowValues, TreeLevel } from '@/types/confunfis';

export const confunfisKey = (materialId: string) => ['confunfis', materialId] as const;
const rowsKey = (materialId: string) => ['confunfis', materialId, 'rows'] as const;
export const rowKey = (materialId: string, rowId: string) => ['confunfis', materialId, 'row', rowId] as const;
export const PAGE_SIZE = 200;

export function useConfunfisSummary(materialId: string) {
  return useQuery({ queryKey: ['confunfis', materialId, 'summary'], queryFn: () => fetchSummary(materialId) });
}

export function useConfunfisRows(materialId: string, filters: RowFilters, page: number, enabled = true) {
  return useQuery({ queryKey: [...rowsKey(materialId), filters, page], queryFn: () => fetchRows(materialId, filters, page, PAGE_SIZE), enabled });
}

export function useConfunfisRow(materialId: string, rowId: string | null) {
  return useQuery({ queryKey: rowKey(materialId, rowId ?? ''), queryFn: () => fetchRow(materialId, rowId ?? ''), enabled: Boolean(rowId) });
}

type Snapshot = [QueryKey, unknown][];

/** Every cached table page and tree level, each row changed (or dropped). */
function mapRows(queryClient: QueryClient, materialId: string, fn: (row: PositionRow) => PositionRow | null): Snapshot {
  const previous = queryClient.getQueriesData<unknown>({ queryKey: confunfisKey(materialId) });
  const apply = (items: PositionRow[]) => items.map(fn).filter((r): r is PositionRow => r !== null);
  for (const [key, data] of previous) {
    if (!data || typeof data !== 'object') continue;
    if (key[2] === 'rows' && 'items' in data) {
      const page = data as RowPage;
      const items = apply(page.items);
      queryClient.setQueryData<RowPage>(key, { ...page, items, total: page.total - (page.items.length - items.length) });
    } else if (key[2] === 'tree' && 'items' in data) {
      const level = data as TreeLevel;
      queryClient.setQueryData<TreeLevel>(key, { ...level, items: apply(level.items), orphans: apply(level.orphans) });
    }
  }
  return previous;
}

function restore(queryClient: QueryClient, previous: Snapshot | undefined): void {
  for (const [key, data] of previous ?? []) queryClient.setQueryData(key, data);
}

/** Whatever the change touches (totals, observations, other rows): read
 *  again -- but the card of a row just removed (`gone`: a 404). */
function refresh(queryClient: QueryClient, materialId: string, gone?: string): void {
  if (gone) queryClient.removeQueries({ queryKey: rowKey(materialId, gone) });
  void queryClient.invalidateQueries({ queryKey: confunfisKey(materialId) });
  void queryClient.invalidateQueries({ queryKey: ['articles'] });
}

/** Editing a row: shown at once in the table and the tree (HR20), the
 *  server's row replaces it, undone if refused (a 409 offers to reload). */
export function useUpdateRow(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ row, values }: { row: PositionRow; values: RowValues }) => updateRow(materialId, row.id, row.version, values),
    onMutate: async ({ row, values }) => {
      await queryClient.cancelQueries({ queryKey: confunfisKey(materialId) });
      const shown: Partial<PositionRow> = Object.fromEntries(Object.entries(values).filter(([k]) => !['article_id', 'noc', 'pn', 'ncage'].includes(k)));
      return { previous: mapRows(queryClient, materialId, (r) => (r.id === row.id ? ({ ...r, ...shown } as PositionRow) : r)) };
    },
    onError: (error, _vars, context) => {
      restore(queryClient, context?.previous);
      notifyError(error, t, () => refresh(queryClient, materialId));
    },
    onSuccess: (saved: RowDetail) => queryClient.setQueryData(rowKey(materialId, saved.id), saved),
    onSettled: () => refresh(queryClient, materialId),
  });
}

/** Removing a row (logically, HR9): it leaves the table and the tree at once. */
export function useDeleteRow(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ row, resetAl }: { row: PositionRow; resetAl?: boolean }) => deleteRow(materialId, row.id, row.version, resetAl),
    onMutate: async ({ row }) => {
      await queryClient.cancelQueries({ queryKey: confunfisKey(materialId) });
      return { previous: mapRows(queryClient, materialId, (r) => (r.id === row.id ? null : r)) };
    },
    onError: (error, _row, context) => {
      restore(queryClient, context?.previous);
      notifyError(error, t, () => refresh(queryClient, materialId));
    },
    onSettled: (_void, error, { row }) => refresh(queryClient, materialId, error ? undefined : row.id),
  });
}

/** A new row, a duplicate as alternative, an alternative CS: not optimistic
 *  (the row's id comes from the server, as a new user's or material's). */
export function useCreateRow(materialId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (values: RowValues) => createRow(materialId, values), onSuccess: () => refresh(queryClient, materialId) });
}

export function useDuplicateAlternative(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (row: PositionRow) => duplicateAlternative(materialId, row.id, row.version),
    onSuccess: () => refresh(queryClient, materialId),
    onError: (error) => notifyError(error, t, () => refresh(queryClient, materialId)),
  });
}

/** "Volver a AL 00" (E14): its id stays, the server's row replaces it. */
export function useResetAl(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (row: PositionRow) => resetAl(materialId, row.id, row.version),
    onMutate: async (row) => {
      await queryClient.cancelQueries({ queryKey: confunfisKey(materialId) });
      return { previous: mapRows(queryClient, materialId, (r) => (r.sns === row.sns && r.co === row.co && r.al === row.al ? { ...r, al: '00' } : r)) };
    },
    onError: (error, _row, context) => {
      restore(queryClient, context?.previous);
      notifyError(error, t, () => refresh(queryClient, materialId));
    },
    onSuccess: (saved: RowDetail) => queryClient.setQueryData(rowKey(materialId, saved.id), saved),
    onSettled: () => refresh(queryClient, materialId),
  });
}

export function useAlternativeCs(materialId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ row, cs }: { row: PositionRow; cs: { cs_sns: string; cs_co: string; cs_al: string } }) => addAlternativeCs(materialId, row.id, row.version, cs),
    onSuccess: () => refresh(queryClient, materialId),
  });
}
