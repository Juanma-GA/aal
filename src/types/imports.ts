// An Excel import job (E03): app/schemas/reference.py ImportJobOut.
export type ImportJobStatus = 'analyzing' | 'analyzed' | 'applied' | 'failed';

export interface ImportIssue {
  code: string;
  params: Record<string, string | number>;
  row: number | null;
  column: string | null;
  header: string | null;
}

/** A field's value in each subcategory, when they differ (CONF_FUN, E12). */
export type Varies = { subcategory: string; value: string }[];

export interface ImportChange {
  field: string;
  header: string;
  before: string;
  after: string;
  varies_before?: Varies;
  varies_after?: Varies;
}

export interface RowCells {
  where: string;
  level: string;
  name: string;
  description: string;
}

/** One subcategory's row of an SNS before and after (CONF_FUN, E12). */
export interface RowDiff {
  subcategory: string | null;
  before: RowCells | null;
  after: RowCells | null;
  changed: (keyof RowCells)[];
}

export interface ImportReport {
  columns: { field: string; header: string }[];
  new: { row: number; key: string; values: Record<string, string> }[];
  modified: { row: number; key: string; changes: ImportChange[]; rows?: RowDiff[] }[];
  unchanged: { row: number; key: string }[];
  /** Only for a target whose import replaces the whole set (CONF_FUN). */
  removed?: { row: null; key: string; values: Record<string, string> }[] | null;
  errors: ImportIssue[];
  warnings: ImportIssue[];
  /** Articles (E12): rows refused with their reasons (they do not block
   *  applying the rest), the AR findings by rule, the AR-008 corrections. */
  rejected?: { row: number; key: string; issues: ImportIssue[] }[] | null;
  ar?: Record<string, { row: number; key: string; name: string; field: string; problem: string; params: Record<string, string | number> }[]> | null;
  corrections?: { row: number; key: string; code: string; field: string; value: string }[] | null;
}

export interface ImportCounts {
  rows: number;
  new: number;
  modified: number;
  unchanged: number;
  removed: number;
  errors: number;
  rows_with_errors: number;
  warnings: number;
}

export interface ImportJob {
  id: string;
  template: string;
  params: Record<string, string>;
  status: ImportJobStatus;
  file_name: string;
  counts: Partial<ImportCounts> & Record<string, number>;
  report: ImportReport | null;
  error_code: string | null;
  error_params: Record<string, string | number>;
  created_at: string;
  analyzed_at: string | null;
  applied_at: string | null;
}
