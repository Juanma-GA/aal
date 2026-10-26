import type {
  Article,
  ArticleChanges,
  ArticleFilters,
  ArticlePage,
  ArticleRights,
  ArticleTemplate,
  BatchResult,
  ExportSummary,
  Finding,
  HistoryEntry,
} from '@/types/articles';
import type { ImportJob } from '@/types/imports';
import { apiFetchFile, apiFetchJson, apiSend, apiUpload } from './apiClient';

const base = '/articles';

function filterQuery(filters: ArticleFilters, extra: Record<string, string | number> = {}): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '' || value === false) continue;
    if (Array.isArray(value)) for (const v of value) q.append(key, v);
    else q.set(key, String(value));
  }
  for (const [key, value] of Object.entries(extra)) q.set(key, String(value));
  return q.toString();
}

export const fetchArticleRights = (): Promise<ArticleRights> => apiFetchJson<ArticleRights>(`${base}/rights`);
export const fetchArticles = (filters: ArticleFilters, page: number): Promise<ArticlePage> =>
  apiFetchJson<ArticlePage>(`${base}?${filterQuery(filters, { page })}`);
export const fetchArticle = (id: string): Promise<Article> => apiFetchJson<Article>(`${base}/${id}`);
export const fetchArticleHistory = (id: string): Promise<HistoryEntry[]> => apiFetchJson<HistoryEntry[]>(`${base}/${id}/history`);
export const fetchArticleFindings = (id: string): Promise<Finding[]> => apiFetchJson<Finding[]>(`${base}/${id}/findings`);
export const createArticle = (body: ArticleChanges & { nombre: string }): Promise<Article> => apiSend<Article>('POST', base, body);
export const updateArticle = (id: string, version: number, changes: ArticleChanges): Promise<Article> =>
  apiSend<Article>('PATCH', `${base}/${id}`, { ...changes, version });
export const deleteArticle = (id: string, version: number): Promise<void> => apiSend<void>('DELETE', `${base}/${id}?version=${version}&confirm=true`);
export const saveArticleBatch = (items: { id: string; version: number; fields: Record<string, string | null> }[]): Promise<BatchResult[]> =>
  apiSend<BatchResult[]>('POST', `${base}/batch`, { items });
export const fetchExportSummary = (filters: ArticleFilters): Promise<ExportSummary> => apiFetchJson<ExportSummary>(`${base}/export-summary?${filterQuery(filters)}`);
export const exportArticles = (template: ArticleTemplate, filters: ArticleFilters) => apiFetchFile(`${base}/export?${filterQuery(filters, { template })}`);
export const startArticleImport = (template: ArticleTemplate, file: File): Promise<ImportJob> => apiUpload<ImportJob>(`${base}/import?template=${template}`, file);
