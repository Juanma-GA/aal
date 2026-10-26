// The article's fields on screen (E12): how the card groups them, and the
// check of a value typed in a cell, from the field's definition
// (article_field_definition: type, length, decimals, S/N values, table) --
// the same rules the server applies, so a cell says what is wrong before
// saving; the server checks again.
import type { ArticleField } from '@/types/reference';

export const NOC_FIELD = 'cdART';
export const NAME_FIELD = 'NomArt';
export const LIFE_CODE_FIELD = 'cdUniVidaA';
export const LIFE_QUANTITY_FIELD = 'caVidaArt';

/** The card's groups (presentation only): PRISMA codes in order. */
export const FIELD_GROUPS: { key: string; fields: string[] }[] = [
  { key: 'identification', fields: [NOC_FIELD, NAME_FIELD] },
  { key: 'logistics', fields: ['cdConjRep', 'cdSegArt', 'cdUsumExtrArt', 'snConsuArt', 'snDocuAdjUArt'] },
  { key: 'maintenance', fields: ['snRepaArt', 'snMtN1Art', 'snMtN2Art', 'snMtN3Art', 'snMtN4Art', 'snMtPreArt'] },
  { key: 'control', fields: ['snCtrlUniArt', 'cdCtrlUniArt', 'snCnfgArt', 'snCtrlVidaArt', LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD] },
  { key: 'dimensions', fields: ['caPesoArt', 'cdUnidPesoArt', 'caLargoArt', 'caAnchoArt', 'caAltoArt', 'cdUnidLongArt', 'caVoluArt', 'cdUnidVoluArt'] },
  { key: 'costs', fields: ['imEstdArt', 'vaUsoArt'] },
  { key: 'pol', fields: ['cdPolEl'] },
];

export const isNumeric = (f: ArticleField): boolean => f.data_type === 'Numérico';
export const isYesNo = (f: ArticleField): boolean => Boolean(f.allowed_values?.length);
/** A code of a reference table (a S/N field's table is only related). */
export const tableOf = (f: ArticleField): string | null => (isYesNo(f) ? null : f.reference_table_code);

export type CellProblem = { code: string; params?: Record<string, string | number> } | null;

/** What is wrong with `raw` for field `f` (null: fine). `codes`: the active
 *  codes of its table, when known; `stored`: the value it already has (a
 *  deactivated code still stands for it). */
export function cellProblem(f: ArticleField, raw: string | null, codes?: Set<string>, stored?: string | null): CellProblem {
  const value = (raw ?? '').trim();
  if (value === '') return null;
  if (isYesNo(f)) return f.allowed_values?.includes(value.toUpperCase()) ? null : { code: 'not_a_choice', params: { allowed: f.allowed_values?.join(', ') ?? '' } };
  if (isNumeric(f)) {
    const text = value.replace(',', '.');
    if (!/^[+-]?\d+(\.\d+)?$/.test(text)) return { code: 'not_decimal' };
    const [whole, fraction = ''] = text.replace(/^[+-]/, '').split('.');
    const decimals = f.decimals ?? 0;
    if (fraction.replace(/0+$/, '').length > decimals) return { code: 'too_many_decimals', params: { max: decimals } };
    const digits = (whole.replace(/^0+/, '') + fraction.padEnd(decimals, '0').slice(0, decimals)).replace(/^0+/, '').length || 1;
    if (f.length !== null && digits > f.length) return { code: 'too_many_digits', params: { max: f.length } };
    return null;
  }
  if (f.length !== null && value.length > f.length) return { code: 'too_long', params: { length: value.length, max: f.length } };
  const table = tableOf(f);
  if (table && codes && !codes.has(value.toUpperCase()) && value.toUpperCase() !== (stored ?? '').toUpperCase()) return { code: 'not_in_table', params: { table } };
  return null;
}

/** A value as it is sent: S/N and codes in upper case, empty as null. */
export function cellValue(f: ArticleField, raw: string | null): string | null {
  const value = (raw ?? '').trim();
  if (value === '') return null;
  if (isNumeric(f)) return value.replace(',', '.');
  return isYesNo(f) || tableOf(f) ? value.toUpperCase() : value;
}
