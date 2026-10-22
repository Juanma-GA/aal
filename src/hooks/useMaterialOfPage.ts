import { useOutletContext } from 'react-router-dom';
import type { Material } from '@/types/auth';

/** The material of the page (inside src/layouts/MaterialLayout.tsx). */
export function useMaterialOfPage(): Material {
  return useOutletContext<Material>();
}
