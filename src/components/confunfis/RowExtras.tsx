// What hangs from a CONFUNFIS row (E14): the parts of its article (read
// here, edited on the article's card), its extra functions (a
// multifunction component, NT §9.1.1) and its incompatibilities with other
// rows. Adding needs confunfis.editar; the server checks it all again.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCreateExtraFunction, useCreateIncompatibility, useDeleteExtraFunction, useDeleteIncompatibility } from '@/hooks/useConfunfisExtras';
import { useReferenceValues } from '@/hooks/useReferenceTables';
import { PARTS_ANCHOR } from '@/components/articles/ArticleParts';
import { ARTICLES_PATH } from '@/pages/articles/ArticlePage';
import { ApiError } from '@/services/apiError';
import { describeApiError } from '@/services/apiErrors';
import { fetchRows } from '@/services/confunfisApi';
import { searchNormalized } from '@/services/cufApi';
import { observationText } from '@/lib/confunfisText';
import { positionOf, type RowDetail } from '@/types/confunfis';
import { INCOMPATIBILITY_KINDS, type ExtraFunction, type Incompatibility, type IncompatibilityKind, type RowRef } from '@/types/confunfisExtras';
import { SearchPick } from './SearchPick';

export const CRITERIA_TABLE = 'CRITERIO_MULTIFUNCION';

function problemsOf(error: unknown): { field: string; code: string; params: Record<string, string> }[] {
  return error instanceof ApiError && error.detail.code === 'confunfis_extra_invalid'
    ? (error.detail.problems as { field: string; code: string; params: Record<string, string> }[])
    : [];
}

function ErrorText({ error }: { error: unknown }): React.JSX.Element | null {
  const { t } = useTranslation();
  if (!error) return null;
  const problems = problemsOf(error);
  return (
    <p className="text-xs text-destructive" role="alert" data-testid="row-extra-error">
      {problems.length
        ? problems.map((p) => t(`confunfis.problems.${p.code}`, { ...p.params, defaultValue: t('confunfis.problems.invalid') })).join(' ')
        : describeApiError(error, t).message}
    </p>
  );
}

function RowName({ row, onOpen }: { row: RowRef; onOpen: (id: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  if (row.deleted) return <span className="text-muted-foreground">{t('confunfis.extras.deletedRow', { position: row.position })}</span>;
  return (
    <button type="button" className="text-left text-link underline-offset-2 hover:underline" onClick={() => onOpen(row.id)}>
      <span className="font-mono text-xs">{row.position}</span> {row.name}
    </button>
  );
}

/** "Partes del artículo": a summary, with the total in this CUF; editing is on the article's card. */
export function PartsSection({ row }: { row: RowDetail }): React.JSX.Element | null {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (!row.article) return null;
  return (
    <section className="flex flex-col gap-1 text-sm" data-testid="row-parts">
      <div className="flex items-center gap-2">
        <h3 className="flex-1 font-medium">{t('confunfis.extras.parts', { count: row.parts.length })}</h3>
        {row.parts.length ? (
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)} aria-expanded={open} data-testid="row-parts-toggle">
            {open ? t('confunfis.extras.hideParts') : t('confunfis.extras.showParts')}
          </Button>
        ) : null}
      </div>
      {open ? (
        <ul className="flex flex-col gap-1" data-testid="row-parts-list">
          {row.parts.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2" data-testid="row-part">
              <span className="font-mono text-xs">{t('confunfis.extras.copAlp', { cop: p.cop, alp: p.alp })}</span>
              <span className="flex-1">{p.article?.nombre ?? p.part_name ?? t('confunfis.noName')}</span>
              <span className="text-xs text-muted-foreground">{t('confunfis.extras.partTotal', { quantity: p.quantity ?? '—', total: p.total ?? '—' })}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <Link to={`${ARTICLES_PATH}/${row.article.id}#${PARTS_ANCHOR}`} className="text-link underline-offset-2 hover:underline" data-testid="row-parts-article">
        {t('confunfis.extras.editParts')}
      </Link>
    </section>
  );
}

/** "Funciones adicionales": the other SNS of a component in one position. */
export function ExtraFunctionsSection({ materialId, row, canEdit }: { materialId: string; row: RowDetail; canEdit: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const criteria = useReferenceValues(CRITERIA_TABLE);
  const create = useCreateExtraFunction(materialId);
  const remove = useDeleteExtraFunction(materialId, row.id);
  const [adding, setAdding] = useState(false);
  const [sns, setSns] = useState<{ sns: string; name: string } | null>(null);
  const [criterion, setCriterion] = useState('');
  const [comment, setComment] = useState('');
  const [removing, setRemoving] = useState<ExtraFunction | null>(null);
  const active = (criteria.data ?? []).filter((c) => c.is_active);
  const label = (code: string) => (criteria.data ?? []).find((c) => c.code === code)?.description ?? code;
  const reset = () => { setAdding(false); setSns(null); setCriterion(''); setComment(''); create.reset(); };
  return (
    <section className="flex flex-col gap-2 text-sm" data-testid="row-extra-functions">
      <div className="flex items-center gap-2">
        <h3 className="flex-1 font-medium">{t('confunfis.extras.extraFunctions', { count: row.extra_functions.length })}</h3>
        {canEdit && !adding ? <Button size="sm" variant="outline" onClick={() => setAdding(true)} data-testid="extra-function-add">{t('confunfis.extras.add')}</Button> : null}
      </div>
      {row.extra_functions.length ? (
        <ul className="flex flex-col gap-1">
          {row.extra_functions.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-2" data-testid={`extra-function-${e.sns}`}>
              <span className="font-mono text-xs">{e.sns}</span>
              <span className="flex-1">{e.sns_name}</span>
              <Badge variant="outline">{label(e.criterion)}</Badge>
              {canEdit ? (
                <Button size="sm" variant="ghost" className="text-destructive" disabled={remove.isPending} onClick={() => setRemoving(e)} data-testid={`extra-function-remove-${e.sns}`}>
                  {t('confunfis.extras.remove')}
                </Button>
              ) : null}
              {e.comment ? <span className="basis-full text-xs text-muted-foreground">{e.comment}</span> : null}
            </li>
          ))}
        </ul>
      ) : <p className="text-muted-foreground">{t('confunfis.extras.noExtraFunctions')}</p>}
      {adding ? (
        <div className="flex flex-col gap-2 rounded-md border p-2" data-testid="extra-function-form">
          <SearchPick<{ sns: string; name: string }>
            id="extra-sns" label={t('confunfis.extras.sns')} placeholder={t('confunfis.form.snsHint')} testId="extra-function-sns"
            picked={sns ? `${sns.sns} · ${sns.name}` : null} onClear={() => setSns(null)} onPick={setSns}
            search={async (q) => (await searchNormalized(materialId, q, 1)).items.filter((n) => n.sns !== row.sns).map((n) => ({ id: n.sns, label: `${n.sns} · ${n.name}`, value: { sns: n.sns, name: n.name } }))}
          />
          <div className="flex flex-col gap-1">
            <Label htmlFor="extra-criterion">{t('confunfis.extras.criterion')}</Label>
            <Select value={criterion} onValueChange={setCriterion}>
              <SelectTrigger id="extra-criterion" className="w-full" data-testid="extra-function-criterion"><SelectValue placeholder={t('confunfis.extras.pick')} /></SelectTrigger>
              <SelectContent>
                {active.map((c) => <SelectItem key={c.code} value={c.code}>{c.description}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="extra-comment">{t('confunfis.extras.comment')}</Label>
            <Input id="extra-comment" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} data-testid="extra-function-comment" />
          </div>
          <ErrorText error={create.error} />
          <div className="flex gap-2">
            <Button
              size="sm" disabled={!sns || !criterion || create.isPending} data-testid="extra-function-save"
              onClick={() => sns && create.mutate({ position_id: row.id, sns: sns.sns, criterion, comment: comment || null }, { onSuccess: reset })}
            >
              {t('actions.save')}
            </Button>
            <Button size="sm" variant="outline" onClick={reset}>{t('actions.cancel')}</Button>
          </div>
        </div>
      ) : null}
      {removing ? (
        <ConfirmDialog
          open onOpenChange={(open) => { if (!open) setRemoving(null); }}
          title={t('confunfis.extras.removeExtraTitle', { sns: removing.sns })}
          description={t('confunfis.extras.removeHint')}
          confirmLabel={t('confunfis.extras.remove')}
          onConfirm={() => { remove.mutate(removing); setRemoving(null); }}
        />
      ) : null}
    </section>
  );
}

/** "Incompatibilidades": "excluye" (both ways) or "requiere" (this row needs the other). */
export function IncompatibilitiesSection({ materialId, row, canEdit, onOpen }: { materialId: string; row: RowDetail; canEdit: boolean; onOpen: (id: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const create = useCreateIncompatibility(materialId);
  const remove = useDeleteIncompatibility(materialId, row.id);
  const [adding, setAdding] = useState(false);
  const [other, setOther] = useState<{ id: string; label: string } | null>(null);
  const [kind, setKind] = useState<IncompatibilityKind>('excluye');
  const [reason, setReason] = useState('');
  const [removing, setRemoving] = useState<Incompatibility | null>(null);
  const reset = () => { setAdding(false); setOther(null); setKind('excluye'); setReason(''); create.reset(); };
  return (
    <section className="flex flex-col gap-2 text-sm" data-testid="row-incompatibilities">
      <div className="flex items-center gap-2">
        <h3 className="flex-1 font-medium">{t('confunfis.extras.incompatibilities', { count: row.incompatibilities.length })}</h3>
        {canEdit && !adding ? <Button size="sm" variant="outline" onClick={() => setAdding(true)} data-testid="incompatibility-add">{t('confunfis.extras.add')}</Button> : null}
      </div>
      {row.incompatibilities.length ? (
        <ul className="flex flex-col gap-2">
          {row.incompatibilities.map((i) => {
            // Seen from this row: "excluye" both ways; "requiere" is "requiere" or "requerida por".
            const mine = i.row_a.id === row.id;
            const verb = i.kind === 'excluye' ? t('confunfis.extras.kinds.excluye') : mine ? t('confunfis.extras.kinds.requiere') : t('confunfis.extras.requiredBy');
            return (
              <li key={i.id} className="flex flex-col gap-1" data-testid={`incompatibility-${i.kind}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{verb}</Badge>
                  <RowName row={mine ? i.row_b : i.row_a} onOpen={onOpen} />
                  {canEdit ? (
                    <Button size="sm" variant="ghost" className="ml-auto text-destructive" disabled={remove.isPending} onClick={() => setRemoving(i)} data-testid="incompatibility-remove">
                      {t('confunfis.extras.remove')}
                    </Button>
                  ) : null}
                </div>
                <span className="text-xs text-muted-foreground">{i.reason}</span>
                {i.observations.map((o) => (
                  <span key={`${o.code}-${o.problem}`} className="text-xs text-warning" data-testid={`incompatibility-observation-${o.code}-${o.problem}`}>{observationText(t, o)}</span>
                ))}
              </li>
            );
          })}
        </ul>
      ) : <p className="text-muted-foreground">{t('confunfis.extras.noIncompatibilities')}</p>}
      {adding ? (
        <div className="flex flex-col gap-2 rounded-md border p-2" data-testid="incompatibility-form">
          <div className="flex flex-col gap-1">
            <Label htmlFor="incompatibility-kind">{t('confunfis.extras.kind')}</Label>
            <Select value={kind} onValueChange={(v) => setKind(v as IncompatibilityKind)}>
              <SelectTrigger id="incompatibility-kind" className="w-full" data-testid="incompatibility-kind"><SelectValue /></SelectTrigger>
              <SelectContent>
                {INCOMPATIBILITY_KINDS.map((k) => <SelectItem key={k} value={k}>{t(`confunfis.extras.kindHints.${k}`)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <SearchPick<{ id: string; label: string }>
            id="incompatibility-row" label={t('confunfis.extras.otherRow')} placeholder={t('confunfis.extras.otherRowHint')} testId="incompatibility-row"
            picked={other?.label ?? null} onClear={() => setOther(null)} onPick={setOther}
            search={async (q) => (await fetchRows(materialId, { q }, 1, 20)).items.filter((r) => r.id !== row.id).map((r) => {
              const text = `${positionOf(r)} · ${r.article_name ?? ''}`;
              return { id: r.id, label: text, value: { id: r.id, label: text } };
            })}
          />
          <div className="flex flex-col gap-1">
            <Label htmlFor="incompatibility-reason">{t('confunfis.extras.reason')}</Label>
            <Input id="incompatibility-reason" value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} data-testid="incompatibility-reason" />
          </div>
          <ErrorText error={create.error} />
          <div className="flex gap-2">
            <Button
              size="sm" disabled={!other || !reason.trim() || create.isPending} data-testid="incompatibility-save"
              onClick={() => other && create.mutate({ row_a_id: row.id, row_b_id: other.id, kind, reason: reason.trim() }, { onSuccess: reset })}
            >
              {t('actions.save')}
            </Button>
            <Button size="sm" variant="outline" onClick={reset}>{t('actions.cancel')}</Button>
          </div>
        </div>
      ) : null}
      {removing ? (
        <ConfirmDialog
          open onOpenChange={(open) => { if (!open) setRemoving(null); }}
          title={t('confunfis.extras.removeIncompatibilityTitle')}
          description={t('confunfis.extras.removeHint')}
          confirmLabel={t('confunfis.extras.remove')}
          onConfirm={() => { remove.mutate(removing); setRemoving(null); }}
        />
      ) : null}
    </section>
  );
}
