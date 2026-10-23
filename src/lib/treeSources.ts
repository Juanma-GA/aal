// Where an SNS tree (src/components/catalog/SnsTree.tsx) reads its levels.
// Callers memoize the result (useMemo): a new source is a new tree.
import type { TreeSource } from '@/components/catalog/SnsTree';
import { fetchTreeLevel } from '@/services/catalogApi';
import { fetchNormalizedLevel } from '@/services/cufApi';
import type { TreeNode } from '@/types/catalog';
import type { NormalizedNode } from '@/types/cuf';

/** A subcategory of a catalog version (E10). */
export function catalogTree(versionId: string, subcategory: string): TreeSource<TreeNode> {
  return { cacheKey: ['catalog', versionId, 'tree', subcategory], loadLevel: (parent) => fetchTreeLevel(versionId, subcategory, parent) };
}

/** A CUF's normalized configuration (E11); `stamp` (its version) renews it. */
export function cufTree(materialId: string, stamp: number): TreeSource<NormalizedNode> {
  return { cacheKey: ['cuf', materialId, 'tree', stamp], loadLevel: (parent) => fetchNormalizedLevel(materialId, parent) };
}
