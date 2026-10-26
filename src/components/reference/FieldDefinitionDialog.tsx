import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useReferenceTables, useUpdateArticleField } from '@/hooks/useReferenceTables';
import { FIELD_IMPORTANCES, type ArticleField, type ArticleFieldChanges } from '@/types/reference';

const NUMERIC = 'Numérico';
const NONE = '__none__';
// The NOC's length is its format (13): not a field's to correct.
const FIXED_LENGTH = new Set(['cdART']);

interface Form {
  name: string;
  importance: string;
  length: string;
  decimals: string;
  related_to: string;
  supplied_by_contractor: string;
  reference_table_code: string;
}

const formOf = (f: ArticleField): Form => ({
  name: f.name, importance: f.importance, length: f.length === null ? '' : String(f.length), decimals: f.decimals === null ? '' : String(f.decimals),
  related_to: f.related_to ?? '', supplied_by_contractor: f.supplied_by_contractor, reference_table_code: f.reference_table_code ?? NONE,
});

/** The admin corrects a field definition (E13) without code: name,
 *  importance, length (digits for a number, without the comma; characters
 *  for a text), decimals, related field, supplier and reference table. The
 *  server refuses a length the stored data would not fit. */
export function FieldDefinitionDialog({ field, onOpenChange }: { field: ArticleField; onOpenChange: (open: boolean) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const tables = useReferenceTables();
  const update = useUpdateArticleField();
  const [form, setForm] = useState<Form>(() => formOf(field));
  const numeric = field.data_type === NUMERIC;
  const withTable = !numeric && !field.allowed_values;
  const set = (patch: Partial<Form>) => setForm({ ...form, ...patch });

  const length = Number(form.length);
  const decimals = form.decimals === '' ? null : Number(form.decimals);
  const lengthInvalid = !Number.isInteger(length) || length < 1;
  const decimalsInvalid = decimals !== null && (!Number.isInteger(decimals) || decimals < 0 || decimals >= length);
  const blocked = !form.name.trim() || !form.supplied_by_contractor.trim() || lengthInvalid || decimalsInvalid;

  const changes = (): ArticleFieldChanges => {
    const out: ArticleFieldChanges = {};
    if (form.name.trim() !== field.name) out.name = form.name.trim();
    if (form.importance !== field.importance) out.importance = form.importance as ArticleFieldChanges['importance'];
    if (length !== field.length) out.length = length;
    if (numeric && decimals !== field.decimals) out.decimals = decimals;
    if ((form.related_to.trim() || null) !== field.related_to) out.related_to = form.related_to.trim() || null;
    if (form.supplied_by_contractor.trim() !== field.supplied_by_contractor) out.supplied_by_contractor = form.supplied_by_contractor.trim();
    const table = form.reference_table_code === NONE ? null : form.reference_table_code;
    if (withTable && table !== field.reference_table_code) out.reference_table_code = table;
    return out;
  };
  const save = () => {
    const c = changes();
    if (Object.keys(c).length) update.mutate({ field, changes: c });
    onOpenChange(false);
  };

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent data-testid="field-definition-dialog">
        <DialogHeader>
          <DialogTitle>{t('articleFields.editTitle', { code: field.prisma_code })}</DialogTitle>
          <DialogDescription>{t('articleFields.editHint')}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1 sm:col-span-2">
            <Label htmlFor="fd-name">{t('articleFields.name')}</Label>
            <Input id="fd-name" value={form.name} onChange={(e) => set({ name: e.target.value })} aria-invalid={!form.name.trim() || undefined} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="fd-importance">{t('articleFields.importance')}</Label>
            <Select value={form.importance} onValueChange={(v) => set({ importance: v })}>
              <SelectTrigger id="fd-importance" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FIELD_IMPORTANCES.map((i) => (
                  <SelectItem key={i} value={i}>
                    {t(`articleFields.importances.${i}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="fd-length">{numeric ? t('articleFields.lengthDigits') : t('articleFields.lengthChars')}</Label>
            <Input
              id="fd-length" inputMode="numeric" value={form.length} onChange={(e) => set({ length: e.target.value })}
              disabled={FIXED_LENGTH.has(field.prisma_code)} aria-invalid={lengthInvalid || undefined} data-testid="fd-length"
            />
          </div>
          {numeric ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor="fd-decimals">{t('articleFields.decimals')}</Label>
              <Input id="fd-decimals" inputMode="numeric" value={form.decimals} onChange={(e) => set({ decimals: e.target.value })} aria-invalid={decimalsInvalid || undefined} data-testid="fd-decimals" />
            </div>
          ) : null}
          {withTable ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor="fd-table">{t('articleFields.referenceTable')}</Label>
              <Select value={form.reference_table_code} onValueChange={(v) => set({ reference_table_code: v })}>
                <SelectTrigger id="fd-table" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>{t('reference.none')}</SelectItem>
                  {(tables.data ?? []).map((tb) => (
                    <SelectItem key={tb.code} value={tb.code}>
                      {tb.code} · {tb.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
          <div className="flex flex-col gap-1">
            <Label htmlFor="fd-related">{t('articleFields.relatedTo')}</Label>
            <Input id="fd-related" value={form.related_to} onChange={(e) => set({ related_to: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="fd-supplied">{t('articleFields.suppliedBy')}</Label>
            <Input id="fd-supplied" value={form.supplied_by_contractor} onChange={(e) => set({ supplied_by_contractor: e.target.value })} />
          </div>
        </div>
        {decimalsInvalid ? <p className="text-sm text-destructive">{t('articleFields.decimalsInvalid')}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('actions.cancel')}
          </Button>
          <Button disabled={blocked} onClick={save} data-testid="fd-save">
            {t('actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
