import type {
  AuditFacets,
  AuditFilters,
  AuditPage,
  Material,
  MaterialFields,
  Member,
  Parameter,
  RoleMatrix,
  User,
  UserWithPassword,
} from '@/types/auth';
import { apiFetchJson, apiSend } from './apiClient';

// ── Materials ─────────────────────────────────────────────────────────────
export const fetchMaterials = (): Promise<Material[]> => apiFetchJson<Material[]>('/materials');
export const createMaterial = (fields: MaterialFields): Promise<Material> => apiSend<Material>('POST', '/materials', fields);
export const updateMaterial = (id: string, version: number, fields: Partial<MaterialFields>): Promise<Material> =>
  apiSend<Material>('PATCH', `/materials/${id}`, { version, ...fields });
export const deleteMaterial = (id: string): Promise<void> => apiSend<void>('DELETE', `/materials/${id}?confirm=true`);
export const fetchMembers = (materialId: string): Promise<Member[]> => apiFetchJson<Member[]>(`/materials/${materialId}/members`);
export const assignMember = (materialId: string, userId: string, role: string): Promise<Member> =>
  apiSend<Member>('PUT', `/materials/${materialId}/members/${userId}`, { role });
export const removeMember = (materialId: string, userId: string): Promise<void> =>
  apiSend<void>('DELETE', `/materials/${materialId}/members/${userId}?confirm=true`);

// ── Users ─────────────────────────────────────────────────────────────────
export const fetchUsers = (): Promise<User[]> => apiFetchJson<User[]>('/users');
export const createUser = (body: { email: string; display_name: string; is_admin: boolean }): Promise<UserWithPassword> =>
  apiSend<UserWithPassword>('POST', '/users', body);
export const updateUser = (
  id: string,
  version: number,
  fields: Partial<Pick<User, 'display_name' | 'is_admin' | 'is_active'>>,
): Promise<User> => apiSend<User>('PATCH', `/users/${id}`, { version, ...fields });
export const resetPassword = (id: string): Promise<UserWithPassword> => apiSend<UserWithPassword>('POST', `/users/${id}/reset-password`);
export const deleteUser = (id: string): Promise<void> => apiSend<void>('DELETE', `/users/${id}?confirm=true`);

// ── Read-only administration ─────────────────────────────────────────────
export const fetchRoles = (): Promise<RoleMatrix> => apiFetchJson<RoleMatrix>('/roles');
export const fetchParameters = (): Promise<Parameter[]> => apiFetchJson<Parameter[]>('/parameters');
export const fetchAuditFacets = (): Promise<AuditFacets> => apiFetchJson<AuditFacets>('/audit/facets');

export function fetchAudit(filters: AuditFilters): Promise<AuditPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return apiFetchJson<AuditPage>(`/audit?${params.toString()}`);
}
