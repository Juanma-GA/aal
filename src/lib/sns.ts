// The level and parent an SNS code implies (NT 10/17 §6, fig. 6-2), the
// same rule as backend/app/services/catalog.py: 000000 or XX0000 sistema,
// XXX000 subsistema, XXXX00 subsubsistema, XXXXX0 conjunto, the rest
// subconjunto; the parent sets the last significant position to 0.
const KEEP = [0, 2, 3, 4, 5];

function depth(sns: string): number {
  if (sns.slice(2) === '0000') return 0;
  if (sns.slice(3) === '000') return 1;
  if (sns.slice(4) === '00') return 2;
  if (sns[5] === '0') return 3;
  return 4;
}

export function derivedParent(sns: string): string | null {
  const d = depth(sns);
  if (d === 0) return null;
  const keep = KEEP[d];
  return sns.slice(0, keep) + '0'.repeat(6 - keep);
}

/** The chain of parents of `sns`, from the top: A21031 -> [A20000, A21000, A21030]. */
export function ancestors(sns: string): string[] {
  const out: string[] = [];
  for (let p = derivedParent(sns); p; p = derivedParent(p)) out.unshift(p);
  return out;
}
