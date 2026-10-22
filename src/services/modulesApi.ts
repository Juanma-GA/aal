import type { Member } from '@/types/auth';
import type { ActivityEntry, ModuleDetail, ModuleGroup, ModuleStatus, TeamMember } from '@/types/modules';
import { apiFetchJson, apiSend } from './apiClient';

export const fetchModules = (): Promise<ModuleGroup[]> => apiFetchJson<ModuleGroup[]>('/modules');
export const fetchModule = (code: string): Promise<ModuleDetail> => apiFetchJson<ModuleDetail>(`/modules/${encodeURIComponent(code)}`);
export const updateModule = (code: string, version: number, status: ModuleStatus, route: string | null): Promise<ModuleDetail> =>
  apiSend<ModuleDetail>('PATCH', `/modules/${encodeURIComponent(code)}`, { version, status, route });

// The material's team as anyone with material.ver sees it (an admin gets
// the full rows, a superset).
export const fetchTeam = (materialId: string): Promise<(TeamMember | Member)[]> =>
  apiFetchJson<(TeamMember | Member)[]>(`/materials/${materialId}/members`);
export const fetchActivity = (materialId: string): Promise<ActivityEntry[]> =>
  apiFetchJson<ActivityEntry[]>(`/materials/${materialId}/activity`);
