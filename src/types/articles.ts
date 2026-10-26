// The article master (E12): app/schemas/articles.py.

export type ArRule = 'AR-001' | 'AR-002' | 'AR-003' | 'AR-004' | 'AR-005' | 'AR-006' | 'AR-007';
export const AR_RULES: ArRule[] = ['AR-001', 'AR-002', 'AR-003', 'AR-004', 'AR-005', 'AR-006', 'AR-007'];
export type NameOrigin = 'coloquial' | 'aprobado' | 'comercial';
export const NAME_ORIGINS: NameOrigin[] = ['coloquial', 'aprobado', 'comercial'];

export interface LifeControl {
  position?: number;
  unit_code: string | null;
  quantity: string | null;
}

export interface ArticleRow {
  id: string;
  noc: string | null;
  pn: string | null;
  ncage: string | null;
  nombre: string;
  origen_nombre: NameOrigin;
  /** PRISMA code -> value (text; numbers as text). */
  fields: Record<string, string | null>;
  life_controls: LifeControl[];
  finding_codes: ArRule[];
  version: number;
}

export interface ArticlePage {
  total: number;
  page: number;
  page_size: number;
  items: ArticleRow[];
}

export interface Finding {
  code: ArRule;
  severity: 'aviso' | 'bloqueante';
  /** PRISMA code of the field to look at. */
  field: string;
  problem: string;
  params: Record<string, string | number>;
}

export interface WhereUsed {
  kind: 'material_cuf' | string;
  material_id?: string;
  material_name?: string;
}

export interface Article extends ArticleRow {
  findings: Finding[];
  where_used: WhereUsed[];
  corrections: { code: string; field: string; value: string }[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
}

export interface ArticleChanges {
  noc?: string | null;
  pn?: string | null;
  ncage?: string | null;
  nombre?: string;
  origen_nombre?: NameOrigin;
  fields?: Record<string, string | null>;
  life_controls?: LifeControl[];
}

export interface ArticleFilters {
  q?: string;
  rule?: ArRule;
  with_findings?: boolean;
  no_noc?: boolean;
  repairable?: 'S' | 'N';
  life_control?: 'S' | 'N';
  group?: string;
  ids?: string[];
}

export interface ArticleRights {
  can_edit: boolean;
  can_import: boolean;
  /** Rows per save of the grid (the "articles" parameter). */
  max_batch_rows: number;
  max_life_controls: number;
}

export interface BatchResult {
  id: string;
  ok: boolean;
  article: ArticleRow | null;
  error: { code: string; [key: string]: unknown } | null;
}

export interface ExportSummary {
  articles: number;
  with_findings: number;
  by_rule: Record<ArRule, number>;
}

export interface HistoryEntry {
  id: string;
  at: string;
  action: string;
  user: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export type ArticleTemplate = 'fichero_carga' | 'maestro';
