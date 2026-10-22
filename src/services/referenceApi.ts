import type { ImportJob } from '@/types/imports';
import type { ArticleField, ReferenceTable, ReferenceValue, ReferenceValueCreate, ReferenceValueUpdate } from '@/types/reference';
import { apiFetchFile, apiFetchJson, apiSend, apiUpload } from './apiClient';

const table = (code: string) => `/reference-tables/${encodeURIComponent(code)}`;

export const fetchReferenceTables = (): Promise<ReferenceTable[]> => apiFetchJson<ReferenceTable[]>('/reference-tables');
export const fetchReferenceTable = (code: string): Promise<ReferenceTable> => apiFetchJson<ReferenceTable>(table(code));
export const fetchReferenceValues = (code: string): Promise<ReferenceValue[]> => apiFetchJson<ReferenceValue[]>(`${table(code)}/values`);
export const createReferenceValue = (code: string, body: ReferenceValueCreate): Promise<ReferenceValue> =>
  apiSend<ReferenceValue>('POST', `${table(code)}/values`, body);
export const updateReferenceValue = (code: string, id: string, body: ReferenceValueUpdate): Promise<ReferenceValue> =>
  apiSend<ReferenceValue>('PATCH', `${table(code)}/values/${id}`, body);
export const fetchArticleFields = (): Promise<ArticleField[]> => apiFetchJson<ArticleField[]>('/article-fields');

export const exportReferenceTable = (code: string) => apiFetchFile(`${table(code)}/export`);
export const startReferenceImport = (code: string, file: File): Promise<ImportJob> => apiUpload<ImportJob>(`${table(code)}/import`, file);
