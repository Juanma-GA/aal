import { Maximize2, Minimize2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { subcategoryLabel } from '@/lib/sns';
import { humanize } from '@/lib/humanize';
import { cn } from '@/lib/utils';
import type { ImportChange, RowCells, RowDiff, Varies } from '@/types/imports';

/** The import dialog's full-screen switch (E16; the size itself is useDialogSize). */
export function FullScreenToggle({ full, onToggle }: { full: boolean; onToggle: () => void }): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <Button type="button" size="sm" variant="ghost" className="self-end" onClick={onToggle} data-testid="import-full-screen">
      {full ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}
      {full ? t('import.normalSize') : t('import.fullScreen')}
    </Button>
  );
}

/** An analysis that failed: its reason and, for an unexpected error, the reference to look up in the log (HR7). */
export function ImportFailure({ code, params, testId }: { code: string | null; params: Record<string, string | number>; testId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const key = code ?? 'import_failed';
  return (
    <Alert variant="destructive" data-testid={testId}>
      <AlertTitle>{t('import.failed')}</AlertTitle>
      <AlertDescription>
        <span>{t(`errors.${key}`, { ...params, defaultValue: humanize(key) })}</span>
        {params.ref ? <span className="block" data-testid={`${testId}-ref`}>{t('import.errorRef', { ref: params.ref })}</span> : null}
      </AlertDescription>
    </Alert>
  );
}

// The category and subcategory names only show when one of them changed:
// the subcategory code already says where the row is.
const COLUMNS: (keyof RowCells)[] = ['level', 'name', 'description'];

/** "Varía por subcategoría" with every value: never one of them picked (HR7). */
export function VariesList({ values }: { values: Varies }): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div data-testid="varies">
      <span className="font-medium text-warning">{t('import.variesBySubcategory')}</span>
      <ul className="mt-1 flex flex-col gap-0.5">
        {values.map((v) => (
          <li key={v.subcategory}>
            <span className="font-mono text-xs">{subcategoryLabel(v.subcategory)}</span> {v.value}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One side of a changed field: its value, or how it varies per subcategory. */
export function ChangeValue({ change, side }: { change: ImportChange; side: 'before' | 'after' }): React.JSX.Element {
  const { t } = useTranslation();
  const varies = side === 'before' ? change.varies_before : change.varies_after;
  if (varies) return <VariesList values={varies} />;
  const value = change[side];
  // An empty value says so: a blank cell reads as "nothing to see" (E15b).
  return value === '' || value === null || value === undefined ? <span className="inline-block italic text-muted-foreground no-underline">{t('import.empty')}</span> : <>{value}</>;
}

/** The rows of an SNS before and after, one line per subcategory, the
 *  columns that changed highlighted. */
export function RowsDiff({ rows }: { rows: RowDiff[] }): React.JSX.Element {
  const { t } = useTranslation();
  const columns: (keyof RowCells)[] = rows.some((r) => r.changed.includes('where')) ? ['where', ...COLUMNS] : COLUMNS;
  const cell = (row: RowDiff, side: 'before' | 'after', column: keyof RowCells) => {
    const cells = row[side];
    const changed = row.changed.includes(column);
    return (
      <TableCell
        key={`${side}-${column}`}
        data-changed={changed ? '' : undefined}
        className={cn('whitespace-normal', side === 'before' ? 'text-muted-foreground' : '', changed ? (side === 'before' ? 'bg-destructive/10' : 'bg-success/15 font-medium') : '')}
      >
        {cells ? cells[column] : '—'}
      </TableCell>
    );
  };
  return (
    <Table data-testid="rows-diff" className="text-xs">
      <TableHeader>
        <TableRow>
          <TableHead rowSpan={2}>{t('import.subcategory')}</TableHead>
          <TableHead colSpan={columns.length}>{t('import.before')}</TableHead>
          <TableHead colSpan={columns.length}>{t('import.after')}</TableHead>
        </TableRow>
        <TableRow>
          {[...columns, ...columns].map((c, i) => (
            <TableHead key={`${c}-${i}`}>{t(`import.rowColumns.${c}`)}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow key={`${row.subcategory ?? '-'}-${i}`} data-subcategory={row.subcategory ?? ''}>
            <TableCell className="font-mono">{row.subcategory ? subcategoryLabel(row.subcategory) : '—'}</TableCell>
            {columns.map((c) => cell(row, 'before', c))}
            {columns.map((c) => cell(row, 'after', c))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
