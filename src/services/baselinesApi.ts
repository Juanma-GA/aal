import type { AuthorizationChangeItem, Baseline, ChangeAuthorization, ConfigurationState, Diff } from '@/types/baselines';
import { apiFetchFile, apiFetchJson, apiSend } from './apiClient';

const base = (materialId: string) => `/materials/${materialId}`;

export const fetchBaselines = (materialId: string): Promise<Baseline[]> => apiFetchJson(`${base(materialId)}/baselines`);
export const fetchConfigurationState = (materialId: string): Promise<ConfigurationState> => apiFetchJson(`${base(materialId)}/baselines/state`);
export const createBaseline = (materialId: string): Promise<Baseline> => apiSend('POST', `${base(materialId)}/baselines`);
export const withdrawBaseline = (materialId: string, b: Baseline): Promise<Baseline> =>
  apiSend('POST', `${base(materialId)}/baselines/${b.id}/withdraw`, { version: b.version });
export const reviewBaseline = (materialId: string, b: Baseline, approve: boolean, comment: string | null): Promise<Baseline> =>
  apiSend('POST', `${base(materialId)}/baselines/${b.id}/${approve ? 'approve' : 'reject'}`, { version: b.version, comment });

const diffQuery = (before: string, after: string, format: 'json' | 'xlsx') => new URLSearchParams({ before, after, format }).toString();
export const fetchDiff = (materialId: string, before: string, after: string): Promise<Diff> =>
  apiFetchJson(`${base(materialId)}/baselines/diff?${diffQuery(before, after, 'json')}`);
export const exportDiff = (materialId: string, before: string, after: string) => apiFetchFile(`${base(materialId)}/baselines/diff?${diffQuery(before, after, 'xlsx')}`);

export const fetchAuthorizations = (materialId: string): Promise<ChangeAuthorization[]> => apiFetchJson(`${base(materialId)}/authorizations`);
export const requestAuthorization = (materialId: string, body: { kind: string; description: string; reason: string }): Promise<ChangeAuthorization> =>
  apiSend('POST', `${base(materialId)}/authorizations`, body);
export const decideAuthorization = (materialId: string, a: ChangeAuthorization, approve: boolean, comment: string | null): Promise<ChangeAuthorization> =>
  apiSend('POST', `${base(materialId)}/authorizations/${a.id}/${approve ? 'approve' : 'reject'}`, { version: a.version, comment });
export const closeAuthorization = (materialId: string, a: ChangeAuthorization): Promise<ChangeAuthorization> =>
  apiSend('POST', `${base(materialId)}/authorizations/${a.id}/close`, { version: a.version });
export const fetchAuthorizationChanges = (materialId: string, id: string): Promise<AuthorizationChangeItem[]> =>
  apiFetchJson(`${base(materialId)}/authorizations/${id}/changes`);
