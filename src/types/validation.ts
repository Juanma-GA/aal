// The NT 10/17 validator (E16): app/schemas/validation.py.

export type Severity = 'bloqueante' | 'aviso' | 'desactivada';
export type LightState = 'red' | 'amber' | 'green' | 'none';

export interface ValidationRule {
  code: string;
  scope: string;
  ref: string;
  active: boolean;
  severity: Severity;
  default_severity: Severity;
  params: Record<string, unknown>;
  help: string | null;
  version: number;
  updated_at: string;
}

export interface Finding {
  id: string;
  rule_code: string;
  severity: 'bloqueante' | 'aviso';
  scope: string;
  entity_type: string;
  entity_id: string;
  problem: string;
  params: Record<string, string>;
  field: string | null;
  row_id: string | null;
  location: string;
  found: string | null;
  accepted: boolean;
  justification: string | null;
  accepted_by: string | null;
  accepted_at: string | null;
}

export interface RuleCount {
  code: string;
  severity: 'bloqueante' | 'aviso';
  ref: string;
  findings: number;
  accepted: number;
}

export interface DeliveryProblem {
  code: string;
  params: Record<string, string | number>;
}

export interface Validation {
  state: LightState;
  outdated: boolean;
  outdated_data: boolean;
  outdated_rules: boolean;
  run_id: string | null;
  at: string | null;
  by: string | null;
  trigger: string | null;
  seconds: number | null;
  blocking: number;
  warnings: number;
  accepted: number;
  by_rule: RuleCount[];
  findings: Finding[];
  delivery_problems: DeliveryProblem[];
}
