// The size of an import dialog (E16): wider than a form, at full screen with
// many changes or when asked; its tables scroll inside it.
import { useState } from 'react';

/** A changed value before and after: a tinted background each, no strike-through,
 *  the text in the normal colour (AA), the new one in medium weight. */
export const BEFORE_CELL = 'whitespace-normal bg-destructive/10 text-foreground';
export const AFTER_CELL = 'whitespace-normal bg-success/15 font-medium text-foreground';
// More changes than this and the report opens at full screen.
const MANY_CHANGES = 50;

export function useDialogSize(changes: number): { full: boolean; toggle: () => void; content: string; scroll: string } {
  // The user's choice, once made; until then, the number of changes decides.
  const [choice, setChoice] = useState<boolean | null>(null);
  const full = choice ?? changes > MANY_CHANGES;
  return {
    full,
    toggle: () => setChoice(!full),
    content: full ? 'flex h-[94vh] flex-col sm:max-w-[96vw]' : 'sm:max-w-6xl',
    scroll: full ? 'max-h-[60vh] overflow-auto' : 'max-h-96 overflow-auto',
  };
}
