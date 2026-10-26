// Texts of the CONFUNFIS (E13) that more than one component writes.
import type { ChainStep, Observation } from '@/types/confunfis';

/** "3 × 6 (A21030) × 1 (A20000) = 18": one path to the CUF. */
export function chainText(chain: ChainStep[], total: string | null): string {
  const factors = chain.map((s) => (s.sns ? `${s.qty ?? '—'} (${s.sns})` : (s.qty ?? '—'))).join(' × ');
  return `${factors} = ${total ?? '—'}`;
}

/** One observation as a sentence, with its data. */
export function observationText(t: (key: string, o?: Record<string, unknown>) => string, o: Observation | { code: string; params: Record<string, string> }): string {
  return t(`confunfis.observations.${o.code}.text`, o.params);
}
