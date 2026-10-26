import { useTranslation } from 'react-i18next';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { subcategoryLabel } from '@/lib/sns';
import { cn } from '@/lib/utils';
import type { ImportChange, RowCells, RowDiff, Varies } from '@/types/imports';

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
  const varies = side === 'before' ? change.varies_before : change.varies_after;
  return varies ? <VariesList values={varies} /> : <>{change[side]}</>;
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
