import type { TFunction } from 'i18next';
import type { CellProblem } from '@/lib/articleFields';

/** What is wrong with a cell, in words: the article's own sentence when
 *  there is one (a code not in its table, an unknown field), else the
 *  import's (a text too long, too many decimals...). */
export function cellProblemText(t: TFunction, p: CellProblem | { code: string; params?: Record<string, string | number> }): string {
  if (!p) return '';
  return t(`articles.cellProblems.${p.code}`, { ...p.params, defaultValue: t(`import.issues.${p.code}`, { ...p.params, value: '' }) });
}
