// Shapes of /api/modules and the Panel's endpoints (backend/app/schemas/).

export type ModuleStatus = 'planificado' | 'en_desarrollo' | 'disponible';

export interface ModuleBrief {
  code: string;
  name: string;
  sort_order: number;
  phase: string;
  status: ModuleStatus;
  route: string | null;
  version: number;
}

export interface ModuleGroup {
  code: string;
  name: string;
  sort_order: number;
  modules: ModuleBrief[];
}

export interface ModuleLink {
  code: string;
  name: string;
  status: ModuleStatus;
  group_code: string;
}

export interface ModuleDetail extends ModuleBrief {
  group_code: string;
  group_name: string;
  encargo: string | null;
  objective: string;
  inputs: string[];
  outputs: string[];
  deliverable: string | null;
  requirements: { rf_id: string; text: string }[];
  depends_on: ModuleLink[];
  used_by: ModuleLink[];
}

export interface TeamMember {
  display_name: string;
  role: string;
}

export interface ActivityEntry {
  created_at: string;
  action: string;
  entity_type: string;
  user_name: string | null;
}
