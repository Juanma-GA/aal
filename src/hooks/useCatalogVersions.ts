import { useQuery } from '@tanstack/react-query';
import { activateCatalogVersion, deleteCatalogVersion, fetchCatalogVersions } from '@/services/catalogApi';
import type { CatalogVersion } from '@/types/catalog';
import { useOptimisticMutation } from './useOptimisticMutation';

export const catalogVersionsKey = ['catalog', 'versions'] as const;

export function useCatalogVersions() {
  return useQuery({ queryKey: catalogVersionsKey, queryFn: fetchCatalogVersions });
}

/** Deleting a version (admin): it leaves the list at once (HR20); the
 *  server refuses the active one and one a CUF uses (rolled back, toast). */
export function useDeleteCatalogVersion() {
  return useOptimisticMutation<CatalogVersion, CatalogVersion, void>({
    queryKey: catalogVersionsKey,
    mutationFn: (v) => deleteCatalogVersion(v.id, v.version),
    apply: (list, v) => list.filter((x) => x.id !== v.id),
    invalidate: [['catalog']],
  });
}

/** Making an older version the active one again (admin). */
export function useActivateCatalogVersion() {
  return useOptimisticMutation<CatalogVersion, CatalogVersion, CatalogVersion>({
    queryKey: catalogVersionsKey,
    mutationFn: (v) => activateCatalogVersion(v.id, v.version),
    apply: (list, v) => list.map((x) => ({ ...x, is_active: x.id === v.id })),
    invalidate: [['catalog']],
  });
}
