// Baselines and change authorizations (E17): app/schemas/baselines.py.
import type { LightState } from '@/types/validation';

export type BaselineState = 'en_revision' | 'revisada' | 'rechazada' | 'retirada';
export type AuthorizationState = 'solicitada' | 'aprobada' | 'rechazada' | 'cerrada';
export type EditState = 'free' | 'locked' | 'authorization';

export interface RunBrief {
  id: string;
  state: LightState;
  blocking: number;
  warnings: number;
  accepted: number;
  at: string;
}

export interface Baseline {
  id: string;
  number: number;
  scope: string;
  state: BaselineState;
  created_at: string;
  created_by: string | null;
  created_by_name: string | null;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  review_comment: string | null;
  validation: RunBrief | null;
  rows: number;
  snapshot_hash: string;
  version: number;
}

export interface ChangeAuthorization {
  id: string;
  code: string;
  number: number;
  kind: string;
  description: string;
  reason: string;
  state: AuthorizationState;
  requested_at: string;
  requested_by: string | null;
  requested_by_name: string | null;
  decided_at: string | null;
  decided_by_name: string | null;
  decision_comment: string | null;
  closed_at: string | null;
  closed_in_baseline: number | null;
  changes: number;
  version: number;
}

export interface ConfigurationState {
  reviewed: Baseline | null;
  in_review: Baseline | null;
  changes_since: number;
  open_authorizations: number;
  usable_authorizations: ChangeAuthorization[];
  edit: EditState;
}

export type DiffEntity = 'row' | 'product' | 'extra' | 'incompatibility' | 'article' | 'part';

export interface DiffEntry {
  entity: DiffEntity;
  id: string;
  label: string;
  change: 'added' | 'removed' | 'modified';
  fields: { field: string; label: string; before: string; after: string }[];
  authorizations: { id: string; code: string }[];
}

export interface Diff {
  before: string;
  after: string;
  entries: DiffEntry[];
}

export interface AuthorizationChangeItem {
  entity_type: string;
  entity_id: string;
  action: string;
  label: string;
  at: string;
  by: string | null;
}

/** "actual": the CONFUNFIS as it is now (the diff's right side). */
export const CURRENT = 'actual';
