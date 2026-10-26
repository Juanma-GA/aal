// Shapes of the auth, users, materials and admin endpoints
// (backend/app/schemas/).

export interface Me {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  must_change_password: boolean;
  ui_preferences: UiPreferences;
}

export type SidebarSide = 'left' | 'right';

export interface UiPreferences {
  active_material_id?: string | null;
  sidebar_collapsed_groups?: string[];
  /** The sidebar folded to its icons (E12). */
  sidebar_folded?: boolean;
  /** Its width in pixels, within UiSettings.sidebar_width. */
  sidebar_width?: number;
  sidebar_side?: SidebarSide;
  /** The docked detail panel's width in pixels (E15), within UiSettings.detail_panel_width. */
  detail_panel_width?: number;
}

/** The interface limits (the "ui" parameter, GET /api/me/ui-settings). */
export interface UiSettings {
  sidebar_width: { min: number; max: number; default: number };
  detail_panel_width: { min: number; max: number; default: number };
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Material {
  id: string;
  noc: string | null;
  name: string;
  part_number: string | null;
  ncage: string | null;
  description: string;
  created_at: string;
  updated_at: string;
  version: number;
  role: string | null;
  permissions: string[];
  /** Stored identifiers without their format (saved before E10). */
  format_problems: ('noc' | 'ncage')[];
  grupo_clase: string | null;
  catalog_version_id: string | null;
  copied_from_material_id: string | null;
}

export interface MaterialFields {
  noc: string | null;
  name: string;
  part_number: string | null;
  ncage: string | null;
  description: string;
  grupo_clase?: string | null;
}

export interface UserMaterial {
  material_id: string;
  material_name: string;
  role: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  deleted_at: string | null;
  version: number;
  materials: UserMaterial[];
}

export interface UserWithPassword {
  user: User;
  temporary_password: string;
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  assigned_at: string;
}

export interface RoleMatrix {
  roles: { code: string }[];
  permissions: { code: string; area: string }[];
  matrix: Record<string, string[]>;
}

export interface AuditEntry {
  id: string;
  created_at: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  material_id: string | null;
  material_name: string | null;
  before: unknown;
  after: unknown;
  ip: string | null;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFacets {
  actions: string[];
  entity_types: string[];
}

export interface AuditFilters {
  user_id?: string;
  material_id?: string;
  entity_type?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
  page: number;
}

export interface Parameter {
  key: string;
  value: Record<string, unknown>;
}
