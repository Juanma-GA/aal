import { Copy, Trash2, Undo2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCreatePart, useDeletePart, useDuplicatePart, useParts, useResetAlp, useUpdatePart } from '@/hooks/useConfunfisExtras';
import { ApiError } from '@/services/apiError';
import { describeApiError } from '@/services/apiErrors';
import { observationText } from '@/lib/confunfisText';
import type { Part } from '@/types/confunfisExtras';

export const PARTS_ANCHOR = 'partes';

const clean = (value: string): string | null => value.trim().toUpperCase() || null;

interface Draft {
  cop: string;
  alp: string;
  quantity: string;
  noc: string;
  pn: string;
  ncage: string;
  part_name: string;
}

const EMPTY: Draft = { cop: '', alp: '00', quantity: '1', noc: '', pn: '', ncage: '', part_name: '' };

/** The parts table of the article (E14, NT §9.1.10): the components of
 *  its breakdown that are in no CONFUNFIS, the same in every CUF that
 *  mounts it. COP 01–99 is the part, ALP 00–99 its alternative (00: none);
 *  the quantity is per unit of the article. The part is found in the master
 *  by NOC, P/N + NCAGE or name (a provisional article otherwise). */
export function ArticleParts({ articleId, canEdit }: { articleId: string; canEdit: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const parts = useParts(articleId);
  const create = useCreatePart(articleId);
  const update = useUpdatePart(articleId);
  const remove = useDeletePart(articleId);
  const duplicate = useDuplicatePart(articleId);
  const reset = useResetAlp(articleId);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [removing, setRemoving] = useState<Part | null>(null);
  const [resetAfter, setResetAfter] = useState(true);
  const list = parts.data ?? [];
  // Opened from a CONFUNFIS row's "Ver partes" (…#partes): brought into view once loaded.
  const { hash } = useLocation();
  const loaded = parts.isSuccess;
  useEffect(() => {
    if (loaded && hash === `#${PARTS_ANCHOR}`) document.getElementById(PARTS_ANCHOR)?.scrollIntoView({ block: 'start' });
  }, [loaded, hash]);
  const problems = create.error instanceof ApiError && create.error.detail.code === 'article_part_invalid'
    ? (create.error.detail.problems as { field: string; code: string; params: Record<string, string> }[])
    : [];
  const problemText = (field: string) => {
    const p = problems.find((x) => x.field === field);
    return p ? <p className="text-xs text-destructive">{t(`confunfis.problems.${p.code}`, { ...p.params, defaultValue: t('confunfis.problems.invalid') })}</p> : null;
  };
  // Removing an ALP that leaves another alone in its COP: back to 00 (offered).
  const leavesSingle = (p: Part) => {
    const alps = new Set(list.filter((x) => x.cop === p.cop && x.id !== p.id).map((x) => x.alp));
    return alps.size === 1 && !alps.has('00');
  };
  const save = () => {
    if (!draft) return;
    create.mutate(
      { cop: draft.cop.trim(), alp: draft.alp.trim() || '00', quantity: draft.quantity.trim() || null, noc: clean(draft.noc), pn: draft.pn.trim() || null, ncage: clean(draft.ncage), part_name: draft.part_name.trim() || null },
      { onSuccess: () => setDraft(null) },
    );
  };
  const field = (key: keyof Draft, label: string, props: React.ComponentProps<typeof Input> = {}) => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`part-${key}`}>{label}</Label>
      <Input id={`part-${key}`} value={draft?.[key] ?? ''} onChange={(e) => setDraft((d) => (d ? { ...d, [key]: e.target.value } : d))} data-testid={`part-form-${key}`} {...props} />
      {problemText(key)}
    </div>
  );

  return (
    <Card id={PARTS_ANCHOR} data-testid="article-parts">
      <CardHeader>
        <CardTitle>{t('articles.parts.title', { count: list.length })}</CardTitle>
        <CardDescription>{t('articles.parts.hint')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {list.length === 0 ? <p className="text-sm text-muted-foreground" data-testid="parts-none">{t('articles.parts.none')}</p> : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">{t('articles.parts.cop')}</TableHead>
                <TableHead className="w-16">{t('articles.parts.alp')}</TableHead>
                <TableHead>{t('articles.parts.part')}</TableHead>
                <TableHead className="w-24">{t('articles.parts.quantity')}</TableHead>
                <TableHead className="w-28"><span className="sr-only">{t('articles.references.actions')}</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((p) => (
                <TableRow key={p.id} data-testid={`part-${p.cop}-${p.alp}`}>
                  <TableCell className="font-mono">{p.cop}</TableCell>
                  <TableCell className="font-mono">{p.alp}</TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      {p.article ? (
                        <Link to={`/articulos/${p.article.id}`} className="text-link underline-offset-2 hover:underline">{p.article.nombre || p.part_name}</Link>
                      ) : <span>{p.part_name ?? '—'}</span>}
                      <span className="font-mono text-xs text-muted-foreground">
                        {[p.article?.noc, p.article?.pn && `${p.article.pn} / ${p.article.ncage ?? ''}`].filter(Boolean).join(' · ')}
                      </span>
                      <span className="flex flex-wrap gap-1">
                        {p.alternative ? <Badge variant="info">{t('confunfis.badges.alternative')}</Badge> : null}
                        {p.article?.origin === 'confunfis' ? <Badge variant="outline" className="border-warning text-warning">{t('confunfis.card.provisional')}</Badge> : null}
                      </span>
                      {p.observations.map((o, i) => (
                        <span key={`${o.code}-${i}`} className="text-xs text-warning" data-testid={`part-observation-${o.code}`}>{observationText(t, o)}</span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <Input
                        key={`${p.id}-${p.version}`} className="h-8 w-20" inputMode="decimal" defaultValue={p.quantity ?? ''} aria-label={t('articles.parts.quantity')}
                        onBlur={(e) => { if (e.target.value.trim() !== (p.quantity ?? '')) update.mutate({ part: p, values: { quantity: e.target.value.trim() || null } }); }}
                        data-testid={`part-quantity-${p.cop}-${p.alp}`}
                      />
                    ) : p.quantity}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <div className="flex justify-end gap-1">
                        {p.observation_codes.includes('OP-006') ? (
                          <Button size="icon" variant="ghost" aria-label={t('articles.parts.resetAlp')} title={t('articles.parts.resetAlp')} onClick={() => reset.mutate(p)}>
                            <Undo2 aria-hidden="true" />
                          </Button>
                        ) : null}
                        <Button size="icon" variant="ghost" aria-label={t('articles.parts.duplicate')} title={t('articles.parts.duplicate')} disabled={duplicate.isPending} onClick={() => duplicate.mutate(p)} data-testid={`part-duplicate-${p.cop}-${p.alp}`}>
                          <Copy aria-hidden="true" />
                        </Button>
                        <Button size="icon" variant="ghost" className="text-destructive" aria-label={t('articles.parts.remove')} onClick={() => { setResetAfter(true); setRemoving(p); }} data-testid={`part-remove-${p.cop}-${p.alp}`}>
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {canEdit && !draft ? (
          <Button variant="outline" className="self-start" onClick={() => { create.reset(); setDraft(EMPTY); }} data-testid="part-add">{t('articles.parts.add')}</Button>
        ) : null}
        {draft ? (
          <div className="flex flex-col gap-3 rounded-md border p-3" data-testid="part-form">
            <p className="text-xs text-muted-foreground">{t('articles.parts.copAlpHelp')}</p>
            <div className="grid grid-cols-3 gap-2">
              {field('cop', t('articles.parts.cop'), { inputMode: 'numeric', maxLength: 2 })}
              {field('alp', t('articles.parts.alp'), { inputMode: 'numeric', maxLength: 2 })}
              {field('quantity', t('articles.parts.quantity'), { inputMode: 'decimal' })}
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {field('noc', t('articles.identity.noc'), { className: 'font-mono' })}
              {field('pn', t('articles.identity.pn'))}
              {field('ncage', t('articles.identity.ncage'))}
            </div>
            {field('part_name', t('articles.parts.name'))}
            <p className="text-xs text-muted-foreground">{t('articles.parts.linkHelp')}</p>
            {create.error && !problems.length ? <p className="text-sm text-destructive" role="alert">{describeApiError(create.error, t).message}</p> : null}
            <div className="flex gap-2">
              <Button disabled={!draft.cop.trim() || create.isPending} onClick={save} data-testid="part-save">{t('actions.save')}</Button>
              <Button variant="outline" onClick={() => setDraft(null)}>{t('actions.cancel')}</Button>
            </div>
          </div>
        ) : null}
      </CardContent>
      {removing ? (
        <ConfirmDialog
          open onOpenChange={(open) => { if (!open) setRemoving(null); }}
          title={t('articles.parts.removeTitle', { cop: removing.cop, alp: removing.alp })}
          description={t('articles.parts.removeHint')}
          confirmLabel={t('articles.parts.remove')}
          onConfirm={() => { remove.mutate({ part: removing, resetAlp: leavesSingle(removing) && resetAfter }); setRemoving(null); }}
        >
          {leavesSingle(removing) ? (
            <div className="flex items-center gap-2 text-sm">
              <Checkbox id="reset-alp" checked={resetAfter} onCheckedChange={(c) => setResetAfter(c === true)} />
              <Label htmlFor="reset-alp">{t('articles.parts.resetAfterRemove')}</Label>
            </div>
          ) : null}
        </ConfirmDialog>
      ) : null}
    </Card>
  );
}
