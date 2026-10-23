import type { Material } from '@/types/auth';
import type { Cuf, Impact, NormalizedNode, NormalizedSearchPage, SnsRequest, SnsRequestFields } from '@/types/cuf';
import { apiFetchFile, apiFetchJson, apiSend } from './apiClient';

const base = (id: string) => `/materials/${id}`;

export const fetchCuf = (id: string): Promise<Cuf> => apiFetchJson<Cuf>(`${base(id)}/cuf`);
export const putSubcategories = (id: string, version: number, codes: string[]): Promise<Cuf> =>
  apiSend<Cuf>('PUT', `${base(id)}/subcategories`, { version, codes });
export const fetchImpact = (id: string, to: string): Promise<Impact> => apiFetchJson<Impact>(`${base(id)}/catalog-version-impact?to=${to}`);
export const changeCatalogVersion = (id: string, version: number, catalogVersionId: string): Promise<Cuf> =>
  apiSend<Cuf>('PUT', `${base(id)}/catalog-version`, { version, catalog_version_id: catalogVersionId, confirm: true });
export const fetchNormalizedLevel = (id: string, parent?: string): Promise<NormalizedNode[]> =>
  apiFetchJson<NormalizedNode[]>(`${base(id)}/normalized-config/tree${parent ? `?parent=${parent}` : ''}`);
export const searchNormalized = (id: string, q: string, page: number): Promise<NormalizedSearchPage> =>
  apiFetchJson<NormalizedSearchPage>(`${base(id)}/normalized-config/search?${new URLSearchParams({ q, page: String(page) })}`);
export const exportNormalized = (id: string) => apiFetchFile(`${base(id)}/normalized-config/export`);
export const copyMaterial = (
  id: string,
  body: { name: string; noc: string | null; part_number: string | null; ncage: string | null; copy_members: boolean },
): Promise<Material> => apiSend<Material>('POST', `${base(id)}/copy`, body);

const requests = (id: string) => `${base(id)}/sns-requests`;
export const fetchSnsRequests = (id: string): Promise<SnsRequest[]> => apiFetchJson<SnsRequest[]>(requests(id));
export const createSnsRequest = (id: string, body: SnsRequestFields): Promise<SnsRequest> => apiSend<SnsRequest>('POST', requests(id), body);
export const updateSnsRequest = (id: string, rid: string, version: number, body: SnsRequestFields): Promise<SnsRequest> =>
  apiSend<SnsRequest>('PATCH', `${requests(id)}/${rid}`, { ...body, version });
export const submitSnsRequest = (id: string, rid: string, version: number): Promise<SnsRequest> =>
  apiSend<SnsRequest>('POST', `${requests(id)}/${rid}/submit`, { version });
export const resolveSnsRequest = (id: string, rid: string, version: number, decision: 'aceptada' | 'rechazada', response: string): Promise<SnsRequest> =>
  apiSend<SnsRequest>('POST', `${requests(id)}/${rid}/resolve`, { version, decision, response });
export const discardSnsRequest = (id: string, rid: string, version: number): Promise<void> =>
  apiSend<void>('DELETE', `${requests(id)}/${rid}?version=${version}&confirm=true`);
export const exportSnsRequests = (id: string) => apiFetchFile(`${requests(id)}/export`);
