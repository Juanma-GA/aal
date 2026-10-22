// An Excel import job (E03): app/schemas/reference.py ImportJobOut.
export type ImportJobStatus = 'analyzing' | 'analyzed' | 'applied' | 'failed';

export interface ImportIssue {
  code: string;
  params: Record<string, string | number>;
  row: number | null;
  column: string | null;
  header: string | null;
}

export interface ImportChange {
  field: string;
  header: string;
  before: string;
  after: string;
}

export interface ImportReport {
  columns: { field: string; header: string }[];
  new: { row: number; key: string; values: Record<string, string> }[];
  modified: { row: number; key: string; changes: ImportChange[] }[];
  unchanged: { row: number; key: string }[];
  errors: ImportIssue[];
  warnings: ImportIssue[];
}

export interface ImportCounts {
  rows: number;
  new: number;
  modified: number;
  unchanged: number;
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
  counts: Partial<ImportCounts>;
  report: ImportReport | null;
  error_code: string | null;
  error_params: Record<string, string | number>;
  created_at: string;
  analyzed_at: string | null;
  applied_at: string | null;
}
