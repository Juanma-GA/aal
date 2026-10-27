// The functional products of the CUF (E14, NT §9.1.11): oils, fuels,
// greases… by POL code, grouped so that N, A and E of one code (what
// replaces what) sit together. Editing needs confunfis.editar.
import { Pencil, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCreateProduct, useDeleteProduct, useProducts, useUpdateProduct } from '@/hooks/useConfunfisExtras';
import { useReferenceValues } from '@/hooks/useReferenceTables';
import { ARTICLES_PATH } from '@/pages/articles/ArticlePage';
import { ApiError } from '@/services/apiError';
import { describeApiError } from '@/services/apiErrors';
import { observationText } from '@/lib/confunfisText';
import type { Product, ProductValues } from '@/types/confunfisExtras';

const NONE = '__none__';
const NAE_ORDER = ['N', 'A', 'E'];
type CodeField = 'pol_code' | 'nae' | 'supply_unit' | 'unit';
// The unit of measure: UNIDAD_MEDIDA_PF (E15), the Anexo XI's L or KG and the D112 codes.
const TABLES: Record<CodeField, string> = { pol_code: 'POL', nae: 'NAE', supply_unit: 'D155', unit: 'UNIDAD_MEDIDA_PF' };

interface Form {
  designation: string;
  pol_code: string;
  nae: string;
  noc: string;
  supply_unit: string;
  quantity: string;
  unit: string;
}

const formOf = (p: Product | null): Form => ({
  designation: p?.designation ?? '', pol_code: p?.pol_code ?? '', nae: p?.nae ?? '', noc: p?.noc ?? '', supply_unit: p?.supply_unit ?? '',
  quantity: p ? (p.quantity ?? '') : '', unit: p?.unit ?? '',
});

/** A code of a reference table, shown with its name; a stored code no
 *  longer in it stays selectable (it is observed, not refused). */
function CodeSelect({ field, value, onChange }: { field: CodeField; value: string; onChange: (code: string, description: string | null) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const values = useReferenceValues(TABLES[field]);
  const active = (values.data ?? []).filter((v) => v.is_active);
  const known = active.some((v) => v.code === value);
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`product-${field}`}>{t(`confunfis.products.fields.${field}`)}</Label>
      <Select value={value || NONE} onValueChange={(v) => { const hit = active.find((x) => x.code === v); onChange(v === NONE ? '' : v, hit?.description ?? null); }}>
        <SelectTrigger id={`product-${field}`} className="w-full" data-testid={`product-form-${field}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="max-h-72">
          <SelectItem value={NONE}>{t('confunfis.products.none')}</SelectItem>
          {value && !known ? <SelectItem value={value}>{t('confunfis.products.notInTable', { code: value })}</SelectItem> : null}
          {active.map((v) => <SelectItem key={v.code} value={v.code}>{`${v.code} · ${v.description}`}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

function ProductDialog({ materialId, product, onClose }: { materialId: string; product: Product | null; onClose: () => void }): React.JSX.Element {
  const { t } = useTranslation();
  const create = useCreateProduct(materialId);
  const update = useUpdateProduct(materialId);
  const [form, setForm] = useState<Form>(() => formOf(product));
  const set = (changes: Partial<Form>) => setForm((f) => ({ ...f, ...changes }));
  const error = create.error;
  const problems = error instanceof ApiError && error.detail.code === 'confunfis_extra_invalid' ? (error.detail.problems as { field: string; code: string }[]) : [];
  const values = (): ProductValues => ({
    designation: form.designation.trim(), pol_code: form.pol_code || null, nae: form.nae || null, noc: form.noc.trim().toUpperCase() || null,
    supply_unit: form.supply_unit || null, quantity: form.quantity.trim() || null, unit: form.unit || null,
  });
  const save = () => {
    if (product) {
      // Optimistic (HR20): the table shows it at once; a refusal undoes it with a toast.
      const original = formOf(product);
      const all = values();
      const changed = Object.fromEntries(Object.entries(all).filter(([k]) => form[k as keyof Form] !== original[k as keyof Form])) as ProductValues;
      if (Object.keys(changed).length) update.mutate({ product, values: changed });
      onClose();
    } else {
      create.mutate(values(), { onSuccess: onClose });
    }
  };
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-2xl" data-testid="product-dialog">
        <DialogHeader>
          <DialogTitle>{product ? t('confunfis.products.editTitle') : t('confunfis.products.newTitle')}</DialogTitle>
          <DialogDescription>{t('confunfis.products.formHint')}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <CodeSelect
              field="pol_code" value={form.pol_code}
              // Its description is proposed as the designation, unless the user wrote one of their own.
              onChange={(code, description) => set({ pol_code: code, ...(description && (!form.designation.trim() || form.designation === (product?.pol_description ?? '')) ? { designation: description } : {}) })}
            />
          </div>
          <div className="flex flex-col gap-1 sm:col-span-2">
            <Label htmlFor="product-designation">{t('confunfis.products.fields.designation')}</Label>
            <Input id="product-designation" value={form.designation} maxLength={200} onChange={(e) => set({ designation: e.target.value })} data-testid="product-form-designation" />
            {problems.some((p) => p.field === 'designation') ? <p className="text-xs text-destructive">{t('confunfis.problems.required')}</p> : null}
          </div>
          <CodeSelect field="nae" value={form.nae} onChange={(code) => set({ nae: code })} />
          <div className="flex flex-col gap-1">
            <Label htmlFor="product-noc">{t('confunfis.products.fields.noc')}</Label>
            <Input id="product-noc" className="font-mono" value={form.noc} maxLength={13} onChange={(e) => set({ noc: e.target.value })} data-testid="product-form-noc" />
          </div>
          <CodeSelect field="supply_unit" value={form.supply_unit} onChange={(code) => set({ supply_unit: code })} />
          <div className="flex flex-col gap-1">
            <Label htmlFor="product-quantity">{t('confunfis.products.fields.quantity')}</Label>
            <Input id="product-quantity" inputMode="decimal" placeholder={t('confunfis.products.bulkHint')} value={form.quantity} onChange={(e) => set({ quantity: e.target.value })} data-testid="product-form-quantity" />
            {problems.some((p) => p.field === 'quantity') ? <p className="text-xs text-destructive">{t('confunfis.problems.not_a_number')}</p> : null}
          </div>
          <CodeSelect field="unit" value={form.unit} onChange={(code) => set({ unit: code })} />
        </div>
        {error && !problems.length ? <p className="text-sm text-destructive" role="alert">{describeApiError(error, t).message}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button disabled={!form.designation.trim() || create.isPending} onClick={save} data-testid="product-save">{t('actions.save')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProductsTable({ materialId, canEdit }: { materialId: string; canEdit: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const products = useProducts(materialId);
  const remove = useDeleteProduct(materialId);
  const [editing, setEditing] = useState<{ product: Product | null } | null>(null);
  const [removing, setRemoving] = useState<Product | null>(null);
  const groups = useMemo(() => {
    const out = new Map<string, Product[]>();
    for (const p of products.data ?? []) {
      const key = p.pol_code ?? '';
      out.set(key, [...(out.get(key) ?? []), p]);
    }
    const rank = (nae: string | null) => (nae && NAE_ORDER.includes(nae) ? NAE_ORDER.indexOf(nae) : NAE_ORDER.length);
    return [...out.entries()]
      .sort(([a], [b]) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b)))
      .map(([code, items]) => ({ code, items: [...items].sort((x, y) => rank(x.nae) - rank(y.nae)) }));
  }, [products.data]);

  if (!products.data) return <Skeleton className="h-64 w-full" />;
  const withObservations = products.data.filter((p) => p.observation_codes.length).length;
  return (
    <div className="flex flex-col gap-4" data-testid="confunfis-products">
      <div className="flex flex-wrap items-center gap-2">
        <Badge data-testid="products-count">{t('confunfis.products.count', { count: products.data.length })}</Badge>
        {withObservations ? <Badge variant="outline" className="border-warning text-warning">{t('confunfis.products.withObservations', { count: withObservations })}</Badge> : null}
        <p className="text-sm text-muted-foreground">{t('confunfis.products.hint')}</p>
        {canEdit ? <Button className="sm:ml-auto" onClick={() => setEditing({ product: null })} data-testid="product-new">{t('confunfis.products.new')}</Button> : null}
      </div>
      {products.data.length === 0 ? <p className="text-sm text-muted-foreground">{t('confunfis.products.empty')}</p> : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">{t('confunfis.products.fields.nae')}</TableHead>
                <TableHead>{t('confunfis.products.fields.designation')}</TableHead>
                <TableHead className="w-36">{t('confunfis.products.fields.noc')}</TableHead>
                <TableHead className="w-28">{t('confunfis.products.fields.supply_unit')}</TableHead>
                <TableHead className="w-24">{t('confunfis.products.fields.quantity')}</TableHead>
                <TableHead className="w-24">{t('confunfis.products.fields.unit')}</TableHead>
                <TableHead className="w-24"><span className="sr-only">{t('articles.references.actions')}</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((g) => (
                <ProductGroup key={g.code || NONE} code={g.code} items={g.items} canEdit={canEdit} onEdit={(p) => setEditing({ product: p })} onRemove={setRemoving} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {editing ? <ProductDialog materialId={materialId} product={editing.product} onClose={() => setEditing(null)} /> : null}
      {removing ? (
        <ConfirmDialog
          open onOpenChange={(open) => { if (!open) setRemoving(null); }}
          title={t('confunfis.products.removeTitle', { name: removing.designation })}
          description={t('confunfis.products.removeHint')}
          confirmLabel={t('confunfis.products.remove')}
          onConfirm={() => { remove.mutate(removing); setRemoving(null); }}
        />
      ) : null}
    </div>
  );
}

function ProductGroup({ code, items, canEdit, onEdit, onRemove }: { code: string; items: Product[]; canEdit: boolean; onEdit: (p: Product) => void; onRemove: (p: Product) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const description = items.find((p) => p.pol_description)?.pol_description;
  return (
    <>
      <TableRow className="bg-muted/50" data-testid={`product-group-${code || 'none'}`}>
        <TableCell colSpan={7} className="font-medium">
          {code ? <span className="font-mono">{code}</span> : t('confunfis.products.noPol')}
          {description ? <span className="ml-2 text-muted-foreground">{description}</span> : null}
        </TableCell>
      </TableRow>
      {items.map((p) => (
        <TableRow key={p.id} data-testid={`product-${p.pol_code ?? 'none'}-${p.nae ?? 'none'}`}>
          <TableCell className="font-mono">{p.nae ?? '—'}</TableCell>
          <TableCell>
            <div className="flex flex-col gap-1">
              <span>{p.designation}</span>
              {p.observations.map((o, i) => (
                <span key={`${o.code}-${i}`} className="text-xs text-warning" data-testid={`product-observation-${o.code}-${o.problem}`}>{observationText(t, o)}</span>
              ))}
            </div>
          </TableCell>
          <TableCell className="font-mono text-xs">
            {p.article ? <Link to={`${ARTICLES_PATH}/${p.article.id}`} className="text-link underline-offset-2 hover:underline">{p.noc}</Link> : (p.noc ?? '—')}
          </TableCell>
          <TableCell className="font-mono">{p.supply_unit ?? '—'}</TableCell>
          <TableCell>{p.quantity ?? t('confunfis.products.bulk')}</TableCell>
          <TableCell className="font-mono">{p.unit ?? '—'}</TableCell>
          <TableCell>
            {canEdit ? (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" aria-label={t('confunfis.products.edit')} onClick={() => onEdit(p)} data-testid="product-edit"><Pencil aria-hidden="true" /></Button>
                <Button size="icon" variant="ghost" className="text-destructive" aria-label={t('confunfis.products.remove')} onClick={() => onRemove(p)} data-testid="product-remove"><Trash2 aria-hidden="true" /></Button>
              </div>
            ) : null}
          </TableCell>
        </TableRow>
      ))}
    </>
  );
}
