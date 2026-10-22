// Display names of the catalogue codes the server sends (roles,
// permissions, audit actions...): from the locale (HR15), and humanized
// when the locale does not have one yet (HR21) -- never the raw code.
import type { TFunction } from 'i18next';
import { humanize } from './humanize';

export type LabelGroup = 'roles' | 'permissions' | 'areas' | 'audit.actions' | 'audit.entities';

export function catalogLabel(t: TFunction, group: LabelGroup, code: string): string {
  // Looked up as an object: the codes have dots ("material.ver") that
  // i18next would otherwise read as nesting.
  const table = t(group, { returnObjects: true }) as Record<string, string> | string;
  const label = typeof table === 'object' ? table[code] : undefined;
  return label ?? humanize(code);
}
