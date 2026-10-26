import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import {
  createExtraFunction,
  createIncompatibility,
  createPart,
  createProduct,
  deleteExtraFunction,
  deleteIncompatibility,
  deletePart,
  deleteProduct,
  duplicatePart,
  fetchCufParts,
  fetchParts,
  fetchProducts,
  resetAlp,
  updatePart,
  updateProduct,
} from '@/services/confunfisExtrasApi';
import type { ExtraFunction, Incompatibility, Part, PartValues, Product, ProductValues } from '@/types/confunfisExtras';
import type { RowDetail } from '@/types/confunfis';
import { confunfisKey, rowKey } from './useConfunfis';
import { useOptimisticMutation } from './useOptimisticMutation';

const productsKey = (materialId: string) => ['confunfis', materialId, 'products'] as const;
export const partsKey = (articleId: string) => ['articles', articleId, 'parts'] as const;

export function useCufParts(materialId: string) {
  return useQuery({ queryKey: ['confunfis', materialId, 'parts'], queryFn: () => fetchCufParts(materialId) });
}

export function useProducts(materialId: string) {
  return useQuery({ queryKey: productsKey(materialId), queryFn: () => fetchProducts(materialId) });
}

export function useParts(articleId: string) {
  return useQuery({ queryKey: partsKey(articleId), queryFn: () => fetchParts(articleId) });
}

/** The observations, totals and counts the change touches: read again. */
function useRefresh() {
  const queryClient = useQueryClient();
  return (materialId?: string) => {
    if (materialId) void queryClient.invalidateQueries({ queryKey: confunfisKey(materialId) });
    else void queryClient.invalidateQueries({ queryKey: ['confunfis'] });
    void queryClient.invalidateQueries({ queryKey: ['articles'] });
  };
}

// ── functional products ──────────────────────────────────────────────

/** A new one: not optimistic (its id comes from the server). */
export function useCreateProduct(materialId: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (values: ProductValues) => createProduct(materialId, values), onSuccess: () => refresh(materialId) });
}

/** Editing shows at once (HR20); the server's product (observations) replaces it. */
export function useUpdateProduct(materialId: string) {
  return useOptimisticMutation<Product, { product: Product; values: ProductValues }, Product>({
    queryKey: productsKey(materialId),
    mutationFn: ({ product, values }) => updateProduct(materialId, product.id, product.version, values),
    apply: (list, { product, values }) => list.map((p) => (p.id === product.id ? ({ ...p, ...values } as Product) : p)),
    settle: (list, saved) => list.map((p) => (p.id === saved.id ? saved : p)),
    invalidate: [confunfisKey(materialId)],
  });
}

export function useDeleteProduct(materialId: string) {
  return useOptimisticMutation<Product, Product, void>({
    queryKey: productsKey(materialId),
    mutationFn: (product) => deleteProduct(materialId, product.id, product.version),
    apply: (list, product) => list.filter((p) => p.id !== product.id),
    invalidate: [confunfisKey(materialId)],
  });
}

// ── extra functions and incompatibilities (on a row's card) ──────────

export function useCreateExtraFunction(materialId: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (values: Parameters<typeof createExtraFunction>[1]) => createExtraFunction(materialId, values), onSuccess: () => refresh(materialId) });
}

export function useCreateIncompatibility(materialId: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (values: Parameters<typeof createIncompatibility>[1]) => createIncompatibility(materialId, values), onSuccess: () => refresh(materialId) });
}

/** Removing one from a row's card: it leaves the card at once (HR20). */
function useRemoveFromCard<T extends { id: string; version: number }>(
  materialId: string, rowId: string, field: 'extra_functions' | 'incompatibilities', remove: (materialId: string, id: string, version: number) => Promise<void>,
) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const refresh = useRefresh();
  const key = rowKey(materialId, rowId);
  return useMutation({
    mutationFn: (item: T) => remove(materialId, item.id, item.version),
    onMutate: async (item: T) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<RowDetail>(key);
      if (previous) {
        const left = (previous[field] as unknown as T[]).filter((x) => x.id !== item.id);
        const count = field === 'extra_functions' ? { extra_function_count: left.length } : { incompatibility_count: left.length };
        queryClient.setQueryData<RowDetail>(key, { ...previous, [field]: left, ...count });
      }
      return { previous };
    },
    onError: (error, _item, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
      notifyError(error, t, () => refresh(materialId));
    },
    onSettled: () => refresh(materialId),
  });
}

export const useDeleteExtraFunction = (materialId: string, rowId: string) => useRemoveFromCard<ExtraFunction>(materialId, rowId, 'extra_functions', deleteExtraFunction);
export const useDeleteIncompatibility = (materialId: string, rowId: string) => useRemoveFromCard<Incompatibility>(materialId, rowId, 'incompatibilities', deleteIncompatibility);

// ── the parts of an article ──────────────────────────────────────────

export function useCreatePart(articleId: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (values: PartValues) => createPart(articleId, values), onSuccess: () => refresh() });
}

export function useUpdatePart(articleId: string) {
  const refresh = useRefresh();
  const mutation = useOptimisticMutation<Part, { part: Part; values: PartValues }, Part>({
    queryKey: partsKey(articleId),
    mutationFn: ({ part, values }) => updatePart(articleId, part.id, part.version, values),
    apply: (list, { part, values }) => list.map((p) => (p.id === part.id ? ({ ...p, ...values } as Part) : p)),
    settle: (list, saved) => list.map((p) => (p.id === saved.id ? saved : p)),
  });
  return { ...mutation, mutate: (vars: { part: Part; values: PartValues }) => mutation.mutate(vars, { onSettled: () => refresh() }) };
}

export function useDeletePart(articleId: string) {
  const refresh = useRefresh();
  const mutation = useOptimisticMutation<Part, { part: Part; resetAlp: boolean }, void>({
    queryKey: partsKey(articleId),
    mutationFn: ({ part, resetAlp: reset }) => deletePart(articleId, part.id, part.version, reset),
    apply: (list, { part }) => list.filter((p) => p.id !== part.id),
  });
  return { ...mutation, mutate: (vars: { part: Part; resetAlp: boolean }) => mutation.mutate(vars, { onSettled: () => refresh() }) };
}

/** "Duplicar como alternativo" and "Volver a ALP 00": the server renumbers. */
export function useDuplicatePart(articleId: string) {
  const refresh = useRefresh();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (part: Part) => duplicatePart(articleId, part.id, part.version),
    onSuccess: () => refresh(),
    onError: (error) => notifyError(error, t, () => refresh()),
  });
}

export function useResetAlp(articleId: string) {
  const refresh = useRefresh();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (part: Part) => resetAlp(articleId, part.id, part.version),
    onSuccess: () => refresh(),
    onError: (error) => notifyError(error, t, () => refresh()),
  });
}
