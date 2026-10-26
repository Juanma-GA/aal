import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCreateRow, useUpdateRow } from '@/hooks/useConfunfis';
import { ApiError } from '@/services/apiError';
import { describeApiError } from '@/services/apiErrors';
import { fetchArticles } from '@/services/articlesApi';
import { fetchNextSlot, fetchRows } from '@/services/confunfisApi';
import { searchNormalized } from '@/services/cufApi';
import { ROOT_POSITION, positionOf, type ArticleBrief, type PositionRow, type RowDetail, type RowValues } from '@/types/confunfis';

const DEBOUNCE_MS = 250;
const NONE = '__none__';

function useDebounced(value: string): string {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setOut(value.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [value]);
  return out;
}

interface Pick<T> {
  id: string;
  label: string;
  value: T;
}

/** A text box with what it finds below; picking one sets it. */
function SearchPick<T>({ id, label, placeholder, picked, onPick, onClear, search, testId }: {
  id: string;
  label: string;
  placeholder: string;
  picked: string | null;
  onPick: (value: T) => void;
  onClear?: () => void;
  search: (q: string) => Promise<Pick<T>[]>;
  testId: string;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const q = useDebounced(text);
  const found = useQuery({ queryKey: ['confunfis-pick', testId, q], queryFn: () => search(q), enabled: q.length > 0 });
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      {picked ? (
        <div className="flex items-center gap-2 text-sm" data-testid={`${testId}-picked`}>
          <span className="flex-1">{picked}</span>
          {onClear ? <Button variant="ghost" size="sm" onClick={onClear}>{t('confunfis.form.change')}</Button> : null}
        </div>
      ) : (
        <>
          <Input id={id} type="search" placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} data-testid={testId} />
          {q && found.data ? (
            <ul className="flex max-h-44 flex-col overflow-auto rounded-md border p-1" data-testid={`${testId}-results`}>
              {found.data.length === 0 ? <li className="px-2 py-1 text-xs text-muted-foreground">{t('confunfis.form.nothingFound')}</li> : null}
              {found.data.map((p) => (
                <li key={p.id}>
                  <button type="button" className="w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={() => { onPick(p.value); setText(''); }} data-testid={`${testId}-hit`}>
                    {p.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
    </div>
  );
}

interface Form {
  sns: string;
  snsName: string | null;
  co: string;
  al: string;
  qty: string;
  article: ArticleBrief | null;
  noc: string;
  pn: string;
  ncage: string;
  article_name: string;
  function_text: string;
  ct_sigle: string;
  cs: string;
}

/** A new row starts with QTY 1, CT SIGLE N and the CUF as CS; an edit with
 *  the row exactly as stored (a blank stays blank: nothing is sent unless
 *  the user changes it). */
const formOf = (row: PositionRow | null): Form => ({
  sns: row?.sns ?? '', snsName: row?.sns_name ?? null, co: row?.co ?? '', al: row ? row.al : '00', qty: row ? (row.qty ?? '') : '1',
  article: row?.article ?? null, noc: '', pn: '', ncage: '', article_name: row?.article_name ?? '', function_text: row?.function_text ?? '',
  ct_sigle: row ? (row.ct_sigle ?? '') : 'N', cs: row ? [row.cs_sns, row.cs_co, row.cs_al].filter(Boolean).join(' ') : ROOT_POSITION,
});

const blank = (v: string): string | null => v.trim() || null;

/** A new row of the CONFUNFIS, or a change to one (E13). The SNS comes from
 *  the CUF's normalized configuration (search), CO and AL are suggested
 *  (the next free CO), the article is found in the master (NOC, P/N or
 *  name) or given by its data (the server links it, or creates a
 *  provisional one), and the CS is chosen from the rows (the CUF if none). */
export function RowFormDialog({ materialId, row, onClose, onSaved }: {
  materialId: string;
  row: PositionRow | null;
  onClose: () => void;
  onSaved: (row: RowDetail) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  const create = useCreateRow(materialId);
  const update = useUpdateRow(materialId);
  const [form, setForm] = useState<Form>(() => formOf(row));
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));
  const error = create.error ?? update.error;
  const problems = error instanceof ApiError && error.detail.code === 'confunfis_row_invalid'
    ? (error.detail.problems as { field: string; code: string; params: Record<string, string> }[])
    : [];
  const problemOf = (field: string) => problems.find((p) => p.field === field || (field === 'cs' && p.field.startsWith('cs')));
  const problemText = (field: string) => {
    const p = problemOf(field);
    return p ? <p className="text-xs text-destructive">{t(`confunfis.problems.${p.code}`, { ...p.params, defaultValue: t('confunfis.problems.invalid') })}</p> : null;
  };

  const chooseSns = (sns: string, name: string) => {
    set({ sns, snsName: name });
    if (!row) fetchNextSlot(materialId, sns).then((slot) => set({ co: slot.co, al: slot.al })).catch(() => undefined);
  };
  const initial = useMemo(() => formOf(row), [row]);
  const values = (): RowValues => {
    // An empty CS is the CUF (NT §9.1.8): shown so, sent as written.
    const [cs_sns, cs_co, cs_al] = form.cs ? form.cs.split(' ') : [null, null, null];
    const all: RowValues = {
      sns: form.sns, co: form.co.trim(), al: form.al.trim() || '00', qty: blank(form.qty), article_name: blank(form.article_name),
      function_text: blank(form.function_text), ct_sigle: form.ct_sigle === 'S' || form.ct_sigle === 'N' ? form.ct_sigle : null,
      cs_sns, cs_co, cs_al,
    };
    const identity: RowValues = form.article
      ? { article_id: form.article.id, pn: blank(form.pn), ncage: blank(form.ncage) }
      : { noc: blank(form.noc), pn: blank(form.pn), ncage: blank(form.ncage) };
    if (!row) return { ...all, ...identity };
    // An edit sends only what the user changed.
    const out: RowValues = {};
    const fields: [keyof Form, (keyof RowValues)[]][] = [
      ['sns', ['sns']], ['co', ['co']], ['al', ['al']], ['qty', ['qty']], ['article_name', ['article_name']],
      ['function_text', ['function_text']], ['ct_sigle', ['ct_sigle']], ['cs', ['cs_sns', 'cs_co', 'cs_al']],
    ];
    for (const [field, keys] of fields) {
      if (form[field] !== initial[field]) for (const k of keys) Object.assign(out, { [k]: all[k] });
    }
    if (form.article?.id !== initial.article?.id || form.noc || form.pn || form.ncage) Object.assign(out, identity);
    return out;
  };
  const save = () => {
    const v = values();
    if (row) {
      if (Object.keys(v).length === 0) { onClose(); return; }
      update.mutate({ row, values: v }, { onSuccess: (saved) => onSaved(saved) });
    } else {
      create.mutate(v, { onSuccess: (saved) => onSaved(saved) });
    }
  };
  const pending = create.isPending || update.isPending;
  const generalError = error && !problems.length ? describeApiError(error, t).message : null;

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="row-form">
        <DialogHeader>
          <DialogTitle>{row ? t('confunfis.form.editTitle', { position: positionOf(row) }) : t('confunfis.form.newTitle')}</DialogTitle>
          <DialogDescription>{t('confunfis.form.hint')}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div className="sm:col-span-4">
            <SearchPick<{ sns: string; name: string }>
              id="row-sns" label={t('confunfis.fields.sns')} placeholder={t('confunfis.form.snsHint')} testId="row-form-sns"
              picked={form.sns ? `${form.sns} · ${form.snsName ?? ''}` : null}
              onClear={() => set({ sns: '', snsName: null })}
              onPick={(v) => chooseSns(v.sns, v.name)}
              search={async (q) => (await searchNormalized(materialId, q, 1)).items.map((n) => ({ id: n.sns, label: `${n.sns} · ${n.name}`, value: { sns: n.sns, name: n.name } }))}
            />
            {problemText('sns')}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-co">{t('confunfis.fields.co')}</Label>
            <Input id="row-co" inputMode="numeric" maxLength={2} value={form.co} onChange={(e) => set({ co: e.target.value })} data-testid="row-form-co" />
            {problemText('co')}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-al">{t('confunfis.fields.al')}</Label>
            <Input id="row-al" inputMode="numeric" maxLength={2} value={form.al} onChange={(e) => set({ al: e.target.value })} data-testid="row-form-al" />
            {problemText('al')}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-qty">{t('confunfis.fields.qty')}</Label>
            <Input id="row-qty" inputMode="decimal" value={form.qty} onChange={(e) => set({ qty: e.target.value })} data-testid="row-form-qty" />
            {problemText('qty')}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-ct">{t('confunfis.fields.ct_sigle')}</Label>
            <Select value={form.ct_sigle || NONE} onValueChange={(v) => set({ ct_sigle: v === NONE ? '' : v })}>
              <SelectTrigger id="row-ct" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t('confunfis.form.blank')}</SelectItem>
                <SelectItem value="S">{t('confunfis.yes')}</SelectItem>
                <SelectItem value="N">{t('confunfis.no')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="sm:col-span-4">
            <SearchPick<ArticleBrief>
              id="row-article" label={t('confunfis.form.article')} placeholder={t('confunfis.form.articleHint')} testId="row-form-article"
              picked={form.article ? `${form.article.nombre}${form.article.noc ? ` · ${form.article.noc}` : ''}` : null}
              onClear={() => set({ article: null })}
              onPick={(a) => set({ article: a, article_name: form.article_name || a.nombre })}
              search={async (q) => (await fetchArticles({ q }, 1)).items.slice(0, 20).map((a) => ({
                id: a.id, label: `${a.nombre}${a.noc ? ` · ${a.noc}` : ''}${a.pn ? ` · ${a.pn}` : ''}`,
                value: { id: a.id, noc: a.noc, pn: a.pn, ncage: a.ncage, nombre: a.nombre, origin: 'maestro' as const },
              }))}
            />
            {!form.article ? <p className="mt-1 text-xs text-muted-foreground">{t('confunfis.form.provisionalHint')}</p> : null}
            {problemText('article_id')}
          </div>
          {!form.article ? (
            <div className="flex flex-col gap-1 sm:col-span-2">
              <Label htmlFor="row-noc">{t('confunfis.fields.noc')}</Label>
              <Input id="row-noc" className="font-mono" value={form.noc} onChange={(e) => set({ noc: e.target.value })} data-testid="row-form-noc" />
              {problemText('noc')}
            </div>
          ) : null}
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-pn">{t('confunfis.fields.pn')}</Label>
            <Input id="row-pn" className="font-mono" value={form.pn} onChange={(e) => set({ pn: e.target.value })} />
            {problemText('pn')}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="row-ncage">{t('confunfis.fields.ncage')}</Label>
            <Input id="row-ncage" className="font-mono" value={form.ncage} onChange={(e) => set({ ncage: e.target.value })} />
            {problemText('ncage')}
          </div>
          <div className="flex flex-col gap-1 sm:col-span-4">
            <Label htmlFor="row-name">{t('confunfis.fields.article_name')}</Label>
            <Input id="row-name" value={form.article_name} onChange={(e) => set({ article_name: e.target.value })} data-testid="row-form-name" />
          </div>
          <div className="flex flex-col gap-1 sm:col-span-4">
            <Label htmlFor="row-function">{t('confunfis.fields.function_text')}</Label>
            <Input id="row-function" value={form.function_text} onChange={(e) => set({ function_text: e.target.value })} data-testid="row-form-function" />
          </div>
          <div className="sm:col-span-4">
            <SearchPick<string>
              id="row-cs" label={t('confunfis.fields.cs')} placeholder={t('confunfis.form.csHint')} testId="row-form-cs"
              picked={form.cs === '?' ? null : !form.cs || form.cs === ROOT_POSITION ? t('confunfis.form.csRoot') : form.cs}
              onClear={() => set({ cs: '?' })}
              onPick={(cs) => set({ cs })}
              search={async (q) => (await fetchRows(materialId, { q }, 1, 20)).items.map((r) => ({ id: r.id, label: `${positionOf(r)} · ${r.article_name ?? ''}`, value: positionOf(r) }))}
            />
            {problemText('cs')}
          </div>
        </div>
        {generalError ? <p className="text-sm text-destructive" role="alert">{generalError}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button disabled={pending || !form.sns || !form.co || form.cs === '?'} onClick={save} data-testid="row-form-save">{t('actions.save')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
