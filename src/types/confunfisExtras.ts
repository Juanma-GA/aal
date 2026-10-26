// The rest of RF-02 (E14): app/schemas/confunfis_extras.py.
import type { ArticleBrief } from './confunfis';

export interface Part {
  id: string;
  parent_article_id: string;
  cop: string;
  alp: string;
  quantity: string | null;
  part_name: string | null;
  article: ArticleBrief | null;
  source: 'manual' | 'seed' | 'import';
  observations: { code: string; params: Record<string, string> }[];
  observation_codes: string[];
  /** Its COP has more than one ALP. */
  alternative: boolean;
  version: number;
  updated_at: string;
}

/** A part in the CUF's "Tabla de partes". */
export interface CufPart extends Part {
  parent: ArticleBrief;
  parent_positions: string[];
  total: string | null;
}

export interface PartValues {
  cop?: string;
  alp?: string | null;
  quantity?: string | null;
  part_name?: string | null;
  article_id?: string | null;
  noc?: string | null;
  pn?: string | null;
  ncage?: string | null;
}

export interface Product {
  id: string;
  designation: string;
  pol_code: string | null;
  pol_description: string | null;
  nae: string | null;
  noc: string | null;
  article: ArticleBrief | null;
  supply_unit: string | null;
  quantity: string | null;
  unit: string | null;
  source: 'manual' | 'seed' | 'import' | 'copia';
  observations: { code: string; params: Record<string, string> }[];
  observation_codes: string[];
  version: number;
  updated_at: string;
}

export interface ProductValues {
  designation?: string;
  pol_code?: string | null;
  nae?: string | null;
  noc?: string | null;
  supply_unit?: string | null;
  quantity?: string | null;
  unit?: string | null;
}

export interface RowRef {
  id: string;
  position: string;
  name: string | null;
  deleted: boolean;
}

export interface ExtraFunction {
  id: string;
  row: RowRef;
  sns: string;
  sns_name: string | null;
  criterion: string;
  comment: string | null;
  source: string;
  version: number;
  updated_at: string;
}

export type IncompatibilityKind = 'excluye' | 'requiere';
export const INCOMPATIBILITY_KINDS: IncompatibilityKind[] = ['excluye', 'requiere'];

export interface Incompatibility {
  id: string;
  row_a: RowRef;
  row_b: RowRef;
  kind: IncompatibilityKind;
  reason: string;
  source: string;
  observations: { code: string; params: Record<string, string> }[];
  observation_codes: string[];
  version: number;
  updated_at: string;
}
