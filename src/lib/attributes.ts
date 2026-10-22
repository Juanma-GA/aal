// A reference value's attributes, readable (HR21): the option's name, Sí/No
// or the number -- never the stored token or the JSON.
import type { TFunction } from 'i18next';
import type { AttributeSpec, AttributeValue } from '@/types/reference';

export function attributeText(spec: AttributeSpec, value: AttributeValue | undefined, t: TFunction): string {
  if (value === undefined || value === null || value === '') return t('reference.none');
  if (spec.type === 'si_no') return value ? t('reference.yes') : t('reference.no');
  if (spec.options.length) return spec.options.find((o) => o.code === value)?.name ?? String(value);
  return String(value);
}

/** Attributes without the empty ones (an absent attribute is not stored). */
export function cleanAttributes(values: Record<string, AttributeValue | undefined>): Record<string, AttributeValue> {
  return Object.fromEntries(
    Object.entries(values).filter((entry): entry is [string, AttributeValue] => entry[1] !== undefined && !(typeof entry[1] === 'number' && Number.isNaN(entry[1]))),
  ) as Record<string, AttributeValue>;
}
