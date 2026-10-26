import type { Categories, CatalogVersion, CatalogWarnings, DiffChange, DiffPage, SearchPage, SnsDetail, TreeNode } from '@/types/catalog';
import type { ImportJob } from '@/types/imports';
import { apiFetchFile, apiFetchJson, apiSend, apiUpload } from './apiClient';

const version = (id: string) => `/catalog/versions/${id}`;
const query = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(Object.entries(params).filter((e): e is [string, string | number] => e[1] !== undefined).map(([k, v]) => [k, String(v)])).toString();

export const fetchCatalogVersions = (): Promise<CatalogVersion[]> => apiFetchJson<CatalogVersion[]>('/catalog/versions');
export const fetchCategories = (id: string): Promise<Categories> => apiFetchJson<Categories>(`${version(id)}/categories`);
export const fetchTreeLevel = (id: string, subcategory: string, parent?: string): Promise<TreeNode[]> =>
  apiFetchJson<TreeNode[]>(`${version(id)}/tree?${query({ subcategory, parent })}`);
export const searchSns = (id: string, q: string, page: number): Promise<SearchPage> => apiFetchJson<SearchPage>(`${version(id)}/search?${query({ q, page })}`);
export const fetchSns = (id: string, sns: string): Promise<SnsDetail> => apiFetchJson<SnsDetail>(`${version(id)}/sns/${encodeURIComponent(sns)}`);
export const fetchCatalogWarnings = (id: string): Promise<CatalogWarnings> => apiFetchJson<CatalogWarnings>(`${version(id)}/warnings`);
export const exportCatalog = (id: string, subcategory?: string) => apiFetchFile(`${version(id)}/export${subcategory ? `?${query({ subcategory })}` : ''}`);
export const startCatalogImport = (file: File): Promise<ImportJob> => apiUpload<ImportJob>('/catalog/import', file);
export const fetchDiff = (from: string, to: string, change: DiffChange | undefined, page: number): Promise<DiffPage> =>
  apiFetchJson<DiffPage>(`/catalog/diff?${query({ from_version: from, to_version: to, change, page })}`);
/** `rowVersion`: the version's optimistic-lock counter. */
export const activateCatalogVersion = (id: string, rowVersion: number): Promise<CatalogVersion> =>
  apiSend<CatalogVersion>('POST', `${version(id)}/activate`, { version: rowVersion, confirm: true });
export const deleteCatalogVersion = (id: string, rowVersion: number): Promise<void> =>
  apiSend<void>('DELETE', `${version(id)}?${query({ version: rowVersion, confirm: 'true' })}`);
