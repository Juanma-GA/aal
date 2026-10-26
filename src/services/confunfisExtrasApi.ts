import type { CufPart, ExtraFunction, Incompatibility, IncompatibilityKind, Part, PartValues, Product, ProductValues } from '@/types/confunfisExtras';
import { apiFetchJson, apiSend } from './apiClient';

const base = (materialId: string) => `/materials/${materialId}/confunfis`;
const parts = (articleId: string) => `/articles/${articleId}/parts`;
const confirm = (version: number) => `?version=${version}&confirm=true`;

// The parts table of an article (global, like the master).
export const fetchParts = (articleId: string): Promise<Part[]> => apiFetchJson(parts(articleId));
export const createPart = (articleId: string, values: PartValues): Promise<Part> => apiSend('POST', parts(articleId), values);
export const updatePart = (articleId: string, partId: string, version: number, values: PartValues): Promise<Part> =>
  apiSend('PATCH', `${parts(articleId)}/${partId}`, { ...values, version });
export const deletePart = (articleId: string, partId: string, version: number, resetAlp = false): Promise<void> =>
  apiSend('DELETE', `${parts(articleId)}/${partId}${confirm(version)}${resetAlp ? '&reset_alp=true' : ''}`);
export const duplicatePart = (articleId: string, partId: string, version: number): Promise<Part> =>
  apiSend('POST', `${parts(articleId)}/${partId}/duplicate-alternative`, { version });
export const resetAlp = (articleId: string, partId: string, version: number): Promise<Part> =>
  apiSend('POST', `${parts(articleId)}/${partId}/reset-alp`, { version });

// The CUF's "Tabla de partes", functional products, extra functions and incompatibilities.
export const fetchCufParts = (materialId: string): Promise<CufPart[]> => apiFetchJson(`${base(materialId)}/parts`);
export const fetchProducts = (materialId: string): Promise<Product[]> => apiFetchJson(`${base(materialId)}/products`);
export const createProduct = (materialId: string, values: ProductValues): Promise<Product> => apiSend('POST', `${base(materialId)}/products`, values);
export const updateProduct = (materialId: string, id: string, version: number, values: ProductValues): Promise<Product> =>
  apiSend('PATCH', `${base(materialId)}/products/${id}`, { ...values, version });
export const deleteProduct = (materialId: string, id: string, version: number): Promise<void> =>
  apiSend('DELETE', `${base(materialId)}/products/${id}${confirm(version)}`);

export const createExtraFunction = (materialId: string, values: { position_id: string; sns: string; criterion: string; comment?: string | null }): Promise<ExtraFunction> =>
  apiSend('POST', `${base(materialId)}/extra-functions`, values);
export const deleteExtraFunction = (materialId: string, id: string, version: number): Promise<void> =>
  apiSend('DELETE', `${base(materialId)}/extra-functions/${id}${confirm(version)}`);

export const createIncompatibility = (materialId: string, values: { row_a_id: string; row_b_id: string; kind: IncompatibilityKind; reason: string }): Promise<Incompatibility> =>
  apiSend('POST', `${base(materialId)}/incompatibilities`, values);
export const deleteIncompatibility = (materialId: string, id: string, version: number): Promise<void> =>
  apiSend('DELETE', `${base(materialId)}/incompatibilities/${id}${confirm(version)}`);
