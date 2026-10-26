import { memo, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FieldInput } from '@/components/articles/FieldInput';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useSaveBatch } from '@/hooks/useArticles';
import { activeCodes } from '@/hooks/useFieldCodes';
import { LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD, NAME_FIELD, NOC_FIELD, cellProblem, cellValue, isNumeric, isYesNo, tableOf, type CellProblem } from '@/lib/articleFields';
import { cellProblemText } from '@/lib/articleText';
import { cn } from '@/lib/utils';
import type { ArticleRow } from '@/types/articles';
import type { ArticleField, ReferenceValue } from '@/types/reference';

const ROW_HEIGHT = 44;
const VIEW_HEIGHT = 560;
const OVERSCAN = 6;
const CELL_WIDTH = 'w-28 min-w-28';

type Draft = Record<string, string | null>;
type Problem = (field: ArticleField, value: string | null, stored: string | null) => CellProblem;

interface RowProps {
  row: ArticleRow;
  draft: Draft | undefined;
  selected: boolean;
  error: string | undefined;
  editable: ArticleField[];
  codes: Record<string, ReferenceValue[]>;
  problem: Problem;
  onCell: (id: string, prisma: string, value: string | null) => void;
  onSelect: (id: string, selected: boolean) => void;
}

/** One row of the grid. Memoized: typing in a cell renders that row only,
 *  never the others. A selector is mounted only while its cell is edited
 *  (the rest show their value): hundreds of mounted Radix selectors were
 *  what made the grid slow (E13). */
const GridRow = memo(function GridRow({ row, draft, selected, error, editable, codes, problem, onCell, onSelect }: RowProps): React.JSX.Element {
  const { t } = useTranslation();
  const [editing, setEditing] = useState<string | null>(null);
  const value = (prisma: string) => (draft && prisma in draft ? draft[prisma] : (row.fields[prisma] ?? null));
  return (
    <tr className={cn('border-b', error ? 'bg-destructive/10' : undefined)} style={{ height: ROW_HEIGHT }} data-testid={`grid-row-${row.nombre}`}>
      <td className="sticky left-0 z-10 bg-card p-2">
        <Checkbox
          checked={selected}
          onCheckedChange={(c) => onSelect(row.id, c === true)}
          aria-label={t('articles.selectRow', { name: row.nombre })}
          data-testid={`grid-select-${row.nombre}`}
        />
      </td>
      <td className="sticky left-10 z-10 w-64 min-w-64 bg-card p-2">
        <span className="block truncate font-medium">{row.nombre}</span>
        <span className="font-mono text-xs text-muted-foreground">{row.noc ?? t('articles.provisional')}</span>
        {error ? <span className="block text-xs text-destructive" data-testid="grid-row-error">{error}</span> : null}
      </td>
      {editable.map((f) => {
        const v = value(f.prisma_code);
        const p = problem(f, v, row.fields[f.prisma_code] ?? null);
        const id = `grid-${row.id}-${f.prisma_code}`;
        const chooser = isYesNo(f) || Boolean(tableOf(f));
        return (
          <td key={f.prisma_code} className={cn(CELL_WIDTH, 'p-1')} title={p ? cellProblemText(t, p) : undefined}>
            {chooser && editing !== f.prisma_code ? (
              <button
                type="button"
                id={id}
                data-testid={id}
                data-field={f.prisma_code}
                aria-invalid={Boolean(p) || undefined}
                aria-label={t('articles.editCell', { field: f.name, name: row.nombre })}
                onClick={() => setEditing(f.prisma_code)}
                onFocus={() => setEditing(f.prisma_code)}
                className="flex h-8 w-full items-center rounded-md border border-input bg-transparent px-2 text-left font-mono text-xs aria-invalid:border-destructive"
              >
                {v ?? t('material.empty')}
              </button>
            ) : chooser ? (
              <FieldInput
                compact
                id={id}
                field={f}
                value={v}
                defaultOpen
                onOpenChange={(open) => !open && setEditing(null)}
                onChange={(next) => onCell(row.id, f.prisma_code, next)}
                values={codes[tableOf(f) ?? '']}
                invalid={Boolean(p)}
              />
            ) : (
              <Input
                id={id}
                data-testid={id}
                data-field={f.prisma_code}
                value={v ?? ''}
                inputMode={isNumeric(f) ? 'decimal' : undefined}
                aria-invalid={Boolean(p) || undefined}
                aria-label={t('articles.editCell', { field: f.name, name: row.nombre })}
                onChange={(e) => onCell(row.id, f.prisma_code, e.target.value === '' ? null : e.target.value)}
                className={cn('h-8 text-xs', isNumeric(f) ? 'text-right font-mono' : undefined)}
              />
            )}
          </td>
        );
      })}
    </tr>
  );
});

/** "Editar en rejilla" (E12): the S/N, code and numeric fields edited in
 *  place, each cell checked as it is typed; "Aplicar a la selección" puts
 *  one value in one field of the selected rows. Saving sends the changed
 *  rows with their versions: a row someone else changed meanwhile is not
 *  overwritten -- it says so and shows the stored data. */
export function ArticleGrid({ rows, fields, codes, onNearEnd, selected, onSelected, maxBatchRows }: {
  rows: ArticleRow[];
  /** Rows per request (the "articles" parameter): more go in several. */
  maxBatchRows: number;
  fields: ArticleField[];
  codes: Record<string, ReferenceValue[]>;
  onNearEnd: () => void;
  selected: Set<string>;
  onSelected: React.Dispatch<React.SetStateAction<Set<string>>>;
}): React.JSX.Element {
  const { t } = useTranslation();
  const editable = useMemo(() => fields.filter((f) => ![NOC_FIELD, NAME_FIELD, LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD].includes(f.prisma_code)), [fields]);
  const defs = useMemo(() => Object.fromEntries(fields.map((f) => [f.prisma_code, f])), [fields]);
  // Each table's active codes, built once (not once per cell and render).
  const codeSets = useMemo(() => Object.fromEntries(Object.entries(codes).map(([table, values]) => [table, activeCodes(values)])), [codes]);
  const problem = useCallback<Problem>((f, v, stored) => {
    const table = tableOf(f);
    return cellProblem(f, v, table ? codeSets[table] : undefined, stored);
  }, [codeSets]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [bulkField, setBulkField] = useState<string>(editable[0]?.prisma_code ?? '');
  const [bulkValue, setBulkValue] = useState<string | null>(null);
  const [scroll, setScroll] = useState(0);
  const save = useSaveBatch();

  const onCell = useCallback((id: string, prisma: string, v: string | null) => setDrafts((d) => ({ ...d, [id]: { ...d[id], [prisma]: v } })), []);
  const onSelect = useCallback(
    (id: string, on: boolean) =>
      onSelected((current) => {
        const next = new Set(current);
        if (on) next.add(id);
        else next.delete(id);
        return next;
      }),
    [onSelected],
  );

  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  // Only the rows with a draft are looked at (not every loaded row).
  const changed = useMemo(
    () =>
      Object.entries(drafts)
        .map(([id, d]) => [byId.get(id), d] as const)
        .filter((e): e is readonly [ArticleRow, Draft] => {
          const row = e[0];
          return row !== undefined && Object.entries(e[1]).some(([p, v]) => cellValue(defs[p], v) !== (row.fields[p] ?? null));
        }),
    [drafts, byId, defs],
  );
  const invalid = useMemo(() => changed.some(([r, d]) => Object.entries(d).some(([p, v]) => problem(defs[p], v, r.fields[p] ?? null))), [changed, defs, problem]);

  const first = Math.max(0, Math.floor(scroll / ROW_HEIGHT) - OVERSCAN);
  const last = Math.min(rows.length, Math.ceil((scroll + VIEW_HEIGHT) / ROW_HEIGHT) + OVERSCAN);
  const shown = rows.slice(first, last);

  const applyToSelection = () => {
    setDrafts((d) => {
      const next = { ...d };
      for (const id of selected) next[id] = { ...next[id], [bulkField]: bulkValue };
      return next;
    });
  };
  const doSave = () => {
    const items = changed.map(([r, d]) => ({
      id: r.id,
      version: r.version,
      fields: Object.fromEntries(Object.entries(d).map(([p, v]) => [p, cellValue(defs[p], v)])),
    }));
    const chunks: (typeof items)[] = [];
    for (let i = 0; i < items.length; i += maxBatchRows) chunks.push(items.slice(i, i + maxBatchRows));
    void (async () => {
      const errors: Record<string, string> = {};
      for (const chunk of chunks) {
        try {
          for (const r of await save.mutateAsync(chunk)) {
            if (!r.ok) errors[r.id] = t(`errors.${r.error?.code ?? 'unexpected'}`, { defaultValue: t('articles.rowNotSaved') });
          }
        } catch {
          // The toast says why; the chunk's rows keep what was typed.
          for (const item of chunk) errors[item.id] = t('articles.rowNotSaved');
        }
      }
      setRowErrors(errors);
      // A saved row shows the server's data; a refused one keeps what was
      // typed, to correct it or save it again once reloaded.
      setDrafts((d) => Object.fromEntries(Object.entries(d).filter(([id]) => id in errors)));
    })();
  };
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const bulkDef = defs[bulkField];

  return (
    <div className="flex flex-col gap-3" data-testid="article-grid">
      <div className="flex flex-wrap items-end gap-2 rounded-md border p-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="bulk-field">{t('articles.bulkField')}</Label>
          <Select value={bulkField} onValueChange={(v) => { setBulkField(v); setBulkValue(null); }}>
            <SelectTrigger id="bulk-field" className="w-64" data-testid="bulk-field">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {editable.map((f) => (
                <SelectItem key={f.prisma_code} value={f.prisma_code}>
                  {f.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {bulkDef ? (
          <div className="flex w-48 flex-col gap-1">
            <Label htmlFor="bulk-value">{t('articles.bulkValue')}</Label>
            <FieldInput id="bulk-value" field={bulkDef} value={bulkValue} onChange={setBulkValue} values={codes[tableOf(bulkDef) ?? '']} />
          </div>
        ) : null}
        <Button variant="outline" disabled={selected.size === 0} onClick={applyToSelection} data-testid="bulk-apply">
          {t('articles.bulkApply', { count: selected.size })}
        </Button>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" disabled={changed.length === 0} onClick={() => setDrafts({})}>
            {t('articles.discardChanges')}
          </Button>
          <Button disabled={changed.length === 0 || invalid || save.isPending} onClick={doSave} data-testid="grid-save">
            {t('articles.saveRows', { count: changed.length })}
          </Button>
        </div>
      </div>
      <div className="overflow-auto rounded-md border" style={{ height: VIEW_HEIGHT }} onScroll={(e) => {
        setScroll(e.currentTarget.scrollTop);
        if (e.currentTarget.scrollTop + VIEW_HEIGHT > (rows.length - 20) * ROW_HEIGHT) onNearEnd();
      }}>
        <table className="w-max text-sm">
          <thead className="sticky top-0 z-20 bg-card">
            <tr className="border-b">
              <th className="sticky left-0 z-20 w-10 bg-card p-2">
                <Checkbox checked={allSelected} onCheckedChange={(c) => onSelected(c ? new Set(rows.map((r) => r.id)) : new Set())} aria-label={t('articles.selectAll')} data-testid="grid-select-all" />
              </th>
              <th className="sticky left-10 z-20 w-64 min-w-64 bg-card p-2 text-left">{t('articles.columns.article')}</th>
              {editable.map((f) => (
                <th key={f.prisma_code} className={cn(CELL_WIDTH, 'p-2 text-left align-bottom font-medium')} title={f.name}>
                  <span className="line-clamp-2 text-xs">{f.name}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{f.prisma_code}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr style={{ height: first * ROW_HEIGHT }} />
            {shown.map((row) => (
              <GridRow
                key={row.id}
                row={row}
                draft={drafts[row.id]}
                selected={selected.has(row.id)}
                error={rowErrors[row.id]}
                editable={editable}
                codes={codes}
                problem={problem}
                onCell={onCell}
                onSelect={onSelect}
              />
            ))}
            <tr style={{ height: Math.max(0, rows.length - last) * ROW_HEIGHT }} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
