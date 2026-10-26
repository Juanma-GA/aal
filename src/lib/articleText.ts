import type { TFunction } from 'i18next';
import type { CellProblem } from '@/lib/articleFields';

/** What is wrong with a cell, in words: the article's own sentence when
 *  there is one (a code not in its table, an unknown field), else the
 *  import's (a text too long, too many decimals...). */
export function cellProblemText(t: TFunction, p: CellProblem | { code: string; params?: Record<string, string | number> }): string {
  if (!p) return '';
  return t(`articles.cellProblems.${p.code}`, { ...p.params, defaultValue: t(`import.issues.${p.code}`, { ...p.params, value: '' }) });
}

/** An AR finding in words, with the fields by their names, never by their
 *  PRISMA codes (HR21). `names`: PRISMA code -> field name. */
export function findingText(
  t: TFunction,
  f: { problem: string; field: string; params: Record<string, string | number> },
  names: Record<string, string>,
): string {
  const name = (code: string) => names[code] ?? code;
  const params: Record<string, string | number> = { ...f.params };
  for (const key of ['flag', 'measure']) if (typeof params[key] === 'string') params[key] = name(params[key]);
  if (typeof params.levels === 'string') params.levels = params.levels.split(', ').map(name).join(', ');
  return t(`articles.problems.${f.problem}`, { ...params, field: name(f.field) });
}
