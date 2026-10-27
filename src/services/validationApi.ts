import type { Severity, Validation, ValidationRule } from '@/types/validation';
import { apiFetchFile, apiFetchJson, apiSend } from './apiClient';

const base = (materialId: string) => `/materials/${materialId}/validation`;

export const fetchValidation = (materialId: string): Promise<Validation> => apiFetchJson(base(materialId));
export const runValidation = (materialId: string): Promise<Validation> => apiSend('POST', base(materialId));
export const acceptFinding = (materialId: string, findingId: string, justification: string): Promise<Validation> =>
  apiSend('POST', `${base(materialId)}/findings/${findingId}/accept`, { justification });
export const exportValidationReport = (materialId: string, format: 'pdf' | 'xlsx') => apiFetchFile(`${base(materialId)}/report?format=${format}`);
export const exportDelivery = (materialId: string) => apiFetchFile(`/materials/${materialId}/confunfis/delivery`);

export const fetchValidationRules = (): Promise<ValidationRule[]> => apiFetchJson('/validation-rules');
export const updateValidationRule = (
  code: string,
  version: number,
  patch: { active?: boolean; severity?: Severity; params?: Record<string, unknown>; help?: string | null },
): Promise<ValidationRule> => apiSend('PATCH', `/validation-rules/${code}`, { ...patch, version });
