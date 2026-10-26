import type { ConfunfisSummary, FunctionalLevel, RowDetail, RowFilters, RowPage, RowValues, TreeLevel, TreeSearch } from '@/types/confunfis';
import { apiFetchJson, apiSend } from './apiClient';

const base = (materialId: string) => `/materials/${materialId}/confunfis`;

function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue;
    q.set(key, String(value));
  }
  const text = q.toString();
  return text ? `?${text}` : '';
}

export const fetchSummary = (materialId: string): Promise<ConfunfisSummary> => apiFetchJson(`${base(materialId)}/summary`);
export const fetchTreeLevel = (materialId: string, parent?: string): Promise<TreeLevel> => apiFetchJson(`${base(materialId)}/tree${query({ parent })}`);
export const fetchFunctional = (materialId: string, parent?: string): Promise<FunctionalLevel> => apiFetchJson(`${base(materialId)}/functional${query({ parent })}`);
export const fetchRows = (materialId: string, filters: RowFilters, page: number, pageSize?: number): Promise<RowPage> =>
  apiFetchJson(`${base(materialId)}/rows${query({ ...filters, page, page_size: pageSize })}`);
export const fetchRow = (materialId: string, rowId: string): Promise<RowDetail> => apiFetchJson(`${base(materialId)}/rows/${rowId}`);
export const fetchNextSlot = (materialId: string, sns: string, co?: string): Promise<{ co: string; al: string }> =>
  apiFetchJson(`${base(materialId)}/next-slot${query({ sns, co })}`);
export const createRow = (materialId: string, values: RowValues): Promise<RowDetail> => apiSend('POST', `${base(materialId)}/rows`, values);
export const updateRow = (materialId: string, rowId: string, version: number, values: RowValues): Promise<RowDetail> =>
  apiSend('PATCH', `${base(materialId)}/rows/${rowId}`, { ...values, version });
export const deleteRow = (materialId: string, rowId: string, version: number, resetAl = false): Promise<void> =>
  apiSend('DELETE', `${base(materialId)}/rows/${rowId}?version=${version}&confirm=true${resetAl ? '&reset_al=true' : ''}`);
export const resetAl = (materialId: string, rowId: string, version: number): Promise<RowDetail> =>
  apiSend('POST', `${base(materialId)}/rows/${rowId}/reset-al`, { version });
export const searchTree = (materialId: string, q: string): Promise<TreeSearch> => apiFetchJson(`${base(materialId)}/search${query({ q })}`);
export const duplicateAlternative = (materialId: string, rowId: string, version: number): Promise<RowDetail> =>
  apiSend('POST', `${base(materialId)}/rows/${rowId}/duplicate-alternative`, { version });
export const addAlternativeCs = (materialId: string, rowId: string, version: number, cs: { cs_sns: string; cs_co: string; cs_al: string }): Promise<RowDetail> =>
  apiSend('POST', `${base(materialId)}/rows/${rowId}/alternative-cs`, { ...cs, version });
