// The CONFUNFIS book (E15): app/services/anexo_xi_import.py's report.
import type { ImportIssue, ImportJob } from './imports';

export type BookMode = 'merge' | 'replace';
export type BookExport = 'anexo' | 'aal' | 'plantilla';
export const BOOK_SHEETS = ['CON_FUN_FIS', 'TABLA PRODUCTOS FUNCIONALES', 'TABLA DE PARTES', 'FUNCIONES ADICIONALES', 'INCOMPATIBILIDADES'] as const;
export const BOOK_CHANGES = ['new', 'modified', 'unchanged', 'removed', 'rejected'] as const;
export type BookChange = (typeof BOOK_CHANGES)[number];

export interface BookItem {
  row: number | null;
  key: string;
  values?: { name?: string };
  changes?: { field: string; header: string; before: string; after: string }[];
  issues?: ImportIssue[];
  not_in_file?: boolean;
}

export type BookSheet = Record<BookChange, BookItem[]>;

export interface BookReport {
  mode: BookMode;
  sheets: Partial<Record<string, BookSheet>>;
  ignored_sheets: string[];
  notices: { code: string }[];
  cuf?: { file: { noc: string[]; pn: string[] }; material: { noc: string | null; pn: string | null; name: string }; differs: boolean };
  result?: {
    observations: Record<string, number>;
    provisional_articles: { noc: string | null; name: string }[];
    new_references: { pn: string; ncage: string | null; article: string }[];
    global_parts: { article: string; noc: string | null; materials: string[]; others: number }[];
  };
  errors: (ImportIssue & { sheet?: string })[];
  warnings: ImportIssue[];
}

export type BookJob = Omit<ImportJob, 'report'> & { report: BookReport | null };
