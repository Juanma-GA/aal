// The CONFUNFIS of a material (E13): app/schemas/confunfis.py.
import type { TreeNode } from './catalog';

export const OBSERVATION_CODES = ['OF-001', 'OF-002', 'OF-003', 'OF-004', 'OF-005', 'OF-006', 'OF-007', 'OF-008', 'OF-009', 'OF-010', 'OF-011', 'OF-012'] as const;
export type ObservationCode = (typeof OBSERVATION_CODES)[number];

export interface Observation {
  code: ObservationCode;
  params: Record<string, string>;
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
  history: { id: string; at: string; action: string; user: string | null }[];
  /** The distinct AL of its hueco (E14). */
  hueco_als: string[];
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
  by_observation: Partial<Record<ObservationCode, number>>;
}

export interface RowFilters {
  sns?: string;
  q?: string;
  with_observations?: boolean;
  observation?: ObservationCode;
  ct_sigle?: 'S' | 'N';
  orphans?: boolean;
  mounted?: boolean;
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
