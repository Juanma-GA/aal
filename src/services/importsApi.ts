import type { ImportJob } from '@/types/imports';
import { apiFetchJson, apiSend } from './apiClient';

export const fetchImportJob = (id: string): Promise<ImportJob> => apiFetchJson<ImportJob>(`/import-jobs/${id}`);
export const applyImportJob = (id: string): Promise<ImportJob> => apiSend<ImportJob>('POST', `/import-jobs/${id}/apply`);
