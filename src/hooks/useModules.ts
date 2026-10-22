import { useQuery } from '@tanstack/react-query';
import { fetchModule, fetchModules } from '@/services/modulesApi';
import type { ModuleBrief } from '@/types/modules';

export const modulesKey = ['modules'] as const;

export function useModules() {
  return useQuery({ queryKey: modulesKey, queryFn: fetchModules });
}

export function useModule(code: string | undefined) {
  return useQuery({ queryKey: ['modules', code], queryFn: () => fetchModule(code ?? ''), enabled: Boolean(code) });
}

/** A module's card for a material. */
export function moduleCardHref(code: string, materialId: string): string {
  return `/materiales/${encodeURIComponent(materialId)}/modulos/${encodeURIComponent(code)}`;
}

/** Where a module opens for a material: an available module's own route
 *  (its :materialId filled in), otherwise its card. */
export function moduleHref(module: Pick<ModuleBrief, 'code' | 'status' | 'route'>, materialId: string): string {
  if (module.status === 'disponible' && module.route) return module.route.replace(':materialId', encodeURIComponent(materialId));
  return moduleCardHref(module.code, materialId);
}
