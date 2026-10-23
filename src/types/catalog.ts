// The normalized functional configuration (E10): app/schemas/catalog.py.
import type { ImportIssue } from '@/types/imports';

export type SnsLevel = 'SISTEMA' | 'SUBSISTEMA' | 'SUBSUBSISTEMA' | 'CONJUNTO' | 'SUBCONJUNTO';

export interface CatalogVersion {
  id: string;
  number: number;
  label: string;
  file_name: string;
  imported_at: string;
  imported_by: string | null;
  is_active: boolean;
  counts: Record<string, number>;
  notes: string;
  version: number;
}

export interface Subcategory {
  code: string;
  sub_code: string;
  name: string;
  sns_count: number;
}

export interface Category {
  code: string;
  name: string;
  subcategories: Subcategory[];
}

export interface Categories {
  categories: Category[];
  uncategorized_rows: number;
}

export interface TreeNode {
  sns: string;
  name: string;
  level: SnsLevel;
  description_pending: boolean;
  child_count: number;
}

export interface SearchHit {
  sns: string;
  name: string;
  level: SnsLevel;
  description_pending: boolean;
  subcategories: string[];
}

export interface SearchPage {
  total: number;
  page: number;
  page_size: number;
  items: SearchHit[];
}

export interface SnsLink {
  sns: string;
  name: string;
  level: SnsLevel;
}

export interface SnsDetail {
  sns: string;
  name: string;
  description: string;
  description_pending: boolean;
  level: SnsLevel;
  declared_levels: string[];
  parent_sns: string | null;
  parent: SnsLink | null;
  children: SnsLink[];
  extra_names: { name: string; origin: 'ELEMENTO' | 'CN-001' | 'OTRA_SUBCATEGORIA' }[];
  appearances: {
    subcategory_code: string | null;
    subcategory_name: string | null;
    category_name: string | null;
    declared_level: string;
    name: string;
    row_number: number;
  }[];
}

export interface CatalogWarnings {
  counts: Record<string, number>;
  items: ImportIssue[];
}

export type DiffChange = 'new' | 'modified' | 'removed';

export interface DiffPage {
  summary: Record<DiffChange | 'unchanged', number>;
  total: number;
  page: number;
  page_size: number;
  items: { sns: string; change: DiffChange; name: string; changes: { field: string; header: string; before: string; after: string }[] }[];
}
