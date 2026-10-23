// The CUF side of a material (E11): app/schemas/cuf.py.
import type { SnsLevel } from '@/types/catalog';

export interface MaterialLink {
  id: string;
  name: string;
}

export interface Cuf {
  material_id: string;
  version: number;
  catalog_version: { id: string; number: number; label: string; is_active: boolean } | null;
  subcategories: { code: string; name: string; category_code: string; category_name: string; sns_count: number }[];
  sns_count: number;
  levels: Partial<Record<SnsLevel, number>>;
  copied_from: MaterialLink | null;
  variants: MaterialLink[];
}

export interface Impact {
  added: string[];
  removed: string[];
  subcategories_missing: string[];
  sns_before: number;
  sns_after: number;
}

export interface NormalizedNode {
  sns: string;
  name: string;
  level: SnsLevel;
  description_pending: boolean;
  child_count: number;
  origins: string[];
}

export interface NormalizedSearchPage {
  total: number;
  page: number;
  page_size: number;
  items: NormalizedNode[];
}

export type SnsRequestState = 'borrador' | 'enviada' | 'aceptada' | 'rechazada';

export interface SnsRequest {
  id: string;
  proposed_sns: string | null;
  parent_sns: string | null;
  name: string;
  function: string;
  justification: string;
  state: SnsRequestState;
  response: string | null;
  created_by: string | null;
  resolved_by: string | null;
  created_at: string;
  sent_at: string | null;
  resolved_at: string | null;
  version: number;
}

export interface SnsRequestFields {
  proposed_sns: string | null;
  parent_sns: string | null;
  name: string;
  function: string;
  justification: string;
}
