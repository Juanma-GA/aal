// Texts of the CONFUNFIS (E13) that more than one component writes.
import type { ChainStep, Observation } from '@/types/confunfis';

/** "3 × 6 (A21030) × 1 (A20000) = 18": one path to the CUF. */
export function chainText(chain: ChainStep[], total: string | null): string {
  const factors = chain.map((s) => (s.sns ? `${s.qty ?? '—'} (${s.sns})` : (s.qty ?? '—'))).join(' × ');
  return `${factors} = ${total ?? '—'}`;
}

/** One finding (E16) as a sentence, with its data. */
export function observationText(t: (key: string, o?: Record<string, unknown>) => string, o: Observation): string {
  return t(`validation.problems.${o.code}.${o.problem}`, { ...o.params, defaultValue: findingTitle(t, o.code) });
}

/** A rule's short name ("SNS fuera de la configuración del CUF"). */
export function findingTitle(t: (key: string, o?: Record<string, unknown>) => string, code: string): string {
  return t(`validation.rules.${code}.title`);
}
