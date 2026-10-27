// The CONFUNFIS of a material (E13): app/schemas/confunfis.py.
import type { TreeNode } from './catalog';
import type { CufPart, ExtraFunction, Incompatibility } from './confunfisExtras';

// The NT 10/17 rules (E16, app/validacion/catalog.py) whose findings are kept on a row.
export const OBSERVATION_CODES = [
  'CF-001', 'CF-002', 'CF-003', 'CF-004', 'CF-005', 'CF-006', 'CF-007', 'CF-008', 'CF-009', 'CF-010', 'CF-011', 'CF-012', 'CF-013', 'CF-014', 'CF-015',
  'CF-017', 'CF-018', 'CF-019', 'CF-020',
] as const;
export type ObservationCode = (typeof OBSERVATION_CODES)[number];

/** A finding of a rule (E16): its code, what is wrong (`problem`) and its data. */
export interface Observation {
  code: string;
  problem: string;
  params: Record<string, string>;
  field?: string;
}

export interface ArticleBrief {
  id: string;
  noc: string | null;
  pn: string | null;
  ncage: string | null;
  nombre: string;
  origin: 'maestro' | 'confunfis';
}

export interface PositionRow {
  id: string;
  sns: string;
  co: string;
  al: string;
  qty: string | null;
  sns_name: string | null;
  article: ArticleBrief | null;
  article_name: string | null;
  function_text: string | null;
  ct_sigle: 'S' | 'N' | null;
  cs_sns: string | null;
  cs_co: string | null;
  cs_al: string | null;
  source: 'manual' | 'seed' | 'import' | 'copia';
  observations: Observation[];
  observation_codes: ObservationCode[];
  /** The hueco's total in the CUF; null: orphan, cycle or no QTY. */
  total: string | null;
  orphan: 'malformed' | 'not_found' | null;
  alternative: boolean;
  cs_alternative: boolean;
  child_count: number;
  is_mounted: boolean;
  mounted: { id: string; name: string } | null;
  /** E14: extra functions (a multifunction component) and incompatibilities. */
  extra_function_count: number;
  incompatibility_count: number;
  version: number;
  updated_at: string;
}

export interface RowPage {
  total: number;
  page: number;
  page_size: number;
  items: PositionRow[];
}

export interface TreeLevel {
  parent: string;
  items: PositionRow[];
  root: PositionRow | null;
  orphans: PositionRow[];
  cycles: string[];
}

export interface ChainStep {
  qty: string | null;
  sns: string | null;
}

export interface RowDetail extends PositionRow {
  parents: PositionRow[];
  children: PositionRow[];
  chains: ChainStep[][];
  history: { id: string; at: string; action: string; user: string | null; authorization: string | null; baseline: number | null }[];
  /** The distinct AL of its hueco (E14). */
  hueco_als: string[];
  /** E14: what hangs from the row, and its article's parts with their total in the CUF. */
  extra_functions: ExtraFunction[];
  incompatibilities: Incompatibility[];
  parts: CufPart[];
}

/** The physical tree's search (E14): each hit with the rows from the CUF
 *  down to its CS. */
export interface TreeSearch {
  total: number;
  hits: { row: PositionRow; path: { id: string; position: string }[] }[];
}

export interface FunctionalNode extends TreeNode {
  row_count: number;
  /** Rows in this SNS and in every SNS below it. */
  rows_below: number;
  /** E14: extra functions of rows elsewhere covering this SNS (and below it). */
  extra_count: number;
  extras_below: number;
}

export interface FunctionalLevel {
  items: FunctionalNode[];
  outside: PositionRow[];
}

export interface ConfunfisSummary {
  rows: number;
  positions: number;
  huecos: number;
  sns_covered: number;
  sns_in_config: number;
  with_observations: number;
  /** Findings kept on the rows, by the rules' severity (E16). */
  errors: number;
  warnings: number;
  by_observation: Partial<Record<ObservationCode, number>>;
  sns_covered_by_extra: number;
  products: number;
  multifunction_rows: number;
  incompatibility_rows: number;
}

export interface RowFilters {
  sns?: string;
  q?: string;
  with_observations?: boolean;
  severity?: 'bloqueante' | 'aviso';
  observation?: ObservationCode;
  ct_sigle?: 'S' | 'N';
  orphans?: boolean;
  mounted?: boolean;
  extra_sns?: string;
  multifunction?: boolean;
  incompatible?: boolean;
}

/** What the form sends (new row or changes). */
export interface RowValues {
  sns?: string;
  co?: string;
  al?: string | null;
  qty?: string | null;
  article_id?: string | null;
  noc?: string | null;
  pn?: string | null;
  ncage?: string | null;
  article_name?: string | null;
  function_text?: string | null;
  ct_sigle?: 'S' | 'N' | null;
  cs_sns?: string | null;
  cs_co?: string | null;
  cs_al?: string | null;
}

export const ROOT_POSITION = '000000 01 00';
export const positionOf = (r: { sns: string; co: string; al: string }): string => `${r.sns} ${r.co} ${r.al}`;
export const csOf = (r: PositionRow): string | null => [r.cs_sns, r.cs_co, r.cs_al].filter(Boolean).join(' ') || null;
