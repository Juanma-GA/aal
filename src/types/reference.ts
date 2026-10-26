// Reference tables (E03): app/schemas/reference.py.
export type AttributeType = 'texto' | 'entero' | 'si_no';
export type AttributeValue = string | number | boolean;

export interface AttributeSpec {
  key: string;
  name: string;
  type: AttributeType;
  required: boolean;
  options: { code: string; name: string }[];
}

export interface ReferenceTable {
  code: string;
  name: string;
  source: string;
  note: string | null;
  editable: boolean;
  attribute_schema: AttributeSpec[];
  value_count: number;
  active_count: number;
  version: number;
}

export interface ReferenceValue {
  id: string;
  code: string;
  description: string;
  definition: string | null;
  attributes: Record<string, AttributeValue>;
  is_active: boolean;
  sort_order: number;
  version: number;
  updated_at: string;
}

export interface ReferenceValueCreate {
  code: string;
  description: string;
  definition: string | null;
  attributes: Record<string, AttributeValue>;
}

export interface ReferenceValueUpdate {
  version: number;
  description?: string;
  definition?: string | null;
  attributes?: Record<string, AttributeValue>;
  is_active?: boolean;
}

export interface ArticleField {
  prisma_code: string;
  name: string;
  importance: string;
  guide_field: string;
  data_type: string;
  length: number | null;
  decimals: number | null;
  related_to: string | null;
  supplied_by_contractor: string;
  reference_table_code: string | null;
  reference_table_name: string | null;
  /** E12: its name in the Fichero Carga, its S/N values, its MAR06 help. */
  header: string | null;
  allowed_values: string[] | null;
  help: FieldHelp | null;
}

/** The MAR06 help of a field (app/seeds/article_field_help.yaml), literal. */
export interface FieldHelp {
  titulo: string | null;
  importancia: string | null;
  tipo: string | null;
  tamano: string | null;
  definicion: string | null;
  finalidad: string | null;
  observaciones: string | null;
}
