import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FieldInput } from '@/components/articles/FieldInput';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useSaveBatch } from '@/hooks/useArticles';
import { activeCodes } from '@/hooks/useFieldCodes';
import { LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD, NAME_FIELD, NOC_FIELD, cellProblem, cellValue, tableOf } from '@/lib/articleFields';
import { cellProblemText } from '@/lib/articleText';
import { cn } from '@/lib/utils';
import type { ArticleRow } from '@/types/articles';
import type { ArticleField, ReferenceValue } from '@/types/reference';

const ROW_HEIGHT = 44;
const VIEW_HEIGHT = 560;
const OVERSCAN = 6;
const CELL_WIDTH = 'w-28 min-w-28';

/** "Editar en rejilla" (E12): the S/N, code and numeric fields edited in
 *  place, each cell checked as it is typed; "Aplicar a la selección" puts
 *  one value in one field of the selected rows. Saving sends the changed
 *  rows with their versions: a row someone else changed meanwhile is not
 *  overwritten -- it says so and shows the stored data. */
export function ArticleGrid({ rows, fields, codes, onNearEnd, selected, onSelected }: {
  rows: ArticleRow[];
  fields: ArticleField[];
  codes: Record<string, ReferenceValue[]>;
  onNearEnd: () => void;
  selected: Set<string>;
  onSelected: (ids: Set<string>) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  const editable = useMemo(() => fields.filter((f) => ![NOC_FIELD, NAME_FIELD, LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD].includes(f.prisma_code)), [fields]);
  const defs = useMemo(() => Object.fromEntries(fields.map((f) => [f.prisma_code, f])), [fields]);
  const [drafts, setDrafts] = useState<Record<string, Record<string, string | null>>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [bulkField, setBulkField] = useState<string>(editable[0]?.prisma_code ?? '');
  const [bulkValue, setBulkValue] = useState<string | null>(null);
  const [scroll, setScroll] = useState(0);
  const save = useSaveBatch();

  const value = (row: ArticleRow, prisma: string) => (drafts[row.id] && prisma in drafts[row.id] ? drafts[row.id][prisma] : (row.fields[prisma] ?? null));
  const setCell = (id: string, prisma: string, v: string | null) => setDrafts((d) => ({ ...d, [id]: { ...d[id], [prisma]: v } }));
  const problem = (row: ArticleRow, prisma: string) => {
    const def = defs[prisma];
    const table = tableOf(def);
    return cellProblem(def, value(row, prisma), table ? activeCodes(codes[table]) : undefined, row.fields[prisma]);
  };
  const changed = rows.filter((r) => drafts[r.id] && Object.entries(drafts[r.id]).some(([p, v]) => cellValue(defs[p], v) !== (r.fields[p] ?? null)));
  const invalid = changed.some((r) => Object.keys(drafts[r.id]).some((p) => problem(r, p)));

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
    const items = changed.map((r) => ({
      id: r.id,
      version: r.version,
      fields: Object.fromEntries(Object.entries(drafts[r.id]).map(([p, v]) => [p, cellValue(defs[p], v)])),
    }));
    save.mutate(items, {
      onSuccess: (results) => {
        const errors: Record<string, string> = {};
        for (const r of results) {
          if (!r.ok) errors[r.id] = t(`errors.${r.error?.code ?? 'unexpected'}`, { defaultValue: t('articles.rowNotSaved') });
        }
        setRowErrors(errors);
        // Saved rows and conflicts alike start from the stored data again.
        setDrafts({});
      },
    });
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
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-b">
              <th className="sticky left-0 z-20 w-10 bg-card p-2">
                <Checkbox checked={allSelected} onCheckedChange={(c) => onSelected(c ? new Set(rows.map((r) => r.id)) : new Set())} aria-label={t('articles.selectAll')} />
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
              <tr key={row.id} className={cn('border-b', rowErrors[row.id] ? 'bg-destructive/10' : undefined)} style={{ height: ROW_HEIGHT }} data-testid={`grid-row-${row.nombre}`}>
                <td className="sticky left-0 z-10 bg-card p-2">
                  <Checkbox
                    checked={selected.has(row.id)}
                    onCheckedChange={(c) => {
                      const next = new Set(selected);
                      if (c) next.add(row.id);
                      else next.delete(row.id);
                      onSelected(next);
                    }}
                    aria-label={t('articles.selectRow', { name: row.nombre })}
                    data-testid={`grid-select-${row.nombre}`}
                  />
                </td>
                <td className="sticky left-10 z-10 w-64 min-w-64 bg-card p-2">
                  <span className="block truncate font-medium">{row.nombre}</span>
                  <span className="font-mono text-xs text-muted-foreground">{row.noc ?? t('articles.provisional')}</span>
                  {rowErrors[row.id] ? <span className="block text-xs text-destructive" data-testid="grid-row-error">{rowErrors[row.id]}</span> : null}
                </td>
                {editable.map((f) => {
                  const p = problem(row, f.prisma_code);
                  return (
                    <td key={f.prisma_code} className={cn(CELL_WIDTH, 'p-1')} title={p ? cellProblemText(t, p) : undefined}>
                      <FieldInput
                        compact
                        id={`grid-${row.id}-${f.prisma_code}`}
                        field={f}
                        value={value(row, f.prisma_code)}
                        onChange={(v) => setCell(row.id, f.prisma_code, v)}
                        values={codes[tableOf(f) ?? '']}
                        invalid={Boolean(p)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr style={{ height: Math.max(0, rows.length - last) * ROW_HEIGHT }} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
