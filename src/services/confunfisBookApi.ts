import type { BookExport, BookJob, BookMode } from '@/types/confunfisBook';
import { apiFetchFile, apiFetchJson, apiSend, apiUpload } from './apiClient';

const base = (materialId: string) => `/materials/${materialId}/confunfis`;

export const startBookImport = (materialId: string, mode: BookMode, file: File): Promise<BookJob> => apiUpload<BookJob>(`${base(materialId)}/import?mode=${mode}`, file);
export const fetchBookJob = (jobId: string): Promise<BookJob> => apiFetchJson<BookJob>(`/import-jobs/${jobId}`);
export const applyBookImport = (materialId: string, jobId: string, confirm: { confirm_cuf: boolean; confirm_name: string | null }): Promise<BookJob> =>
  apiSend<BookJob>('POST', `${base(materialId)}/import/${jobId}/apply`, confirm);
export const exportBook = (materialId: string, kind: BookExport) => apiFetchFile(`${base(materialId)}/export?kind=${kind}`);
