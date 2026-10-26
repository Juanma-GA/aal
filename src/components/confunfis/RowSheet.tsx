import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { DetailPanel } from '@/components/layout/DetailPanel';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useConfunfisRow, useDeleteRow, useDuplicateAlternative, useResetAl } from '@/hooks/useConfunfis';
import { ARTICLES_PATH } from '@/pages/articles/ArticlePage';
import { chainText, observationText } from '@/lib/confunfisText';
import { csOf, positionOf, type PositionRow } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';
import { ExtraFunctionsSection, IncompatibilitiesSection, PartsSection } from './RowExtras';

function RowLink({ row, onOpen }: { row: PositionRow; onOpen: (id: string) => void }): React.JSX.Element {
  return (
    <button type="button" className="text-left text-link underline-offset-2 hover:underline" onClick={() => onOpen(row.id)}>
      <span className="font-mono text-xs">{positionOf(row)}</span> {row.article_name}
    </button>
  );
}

interface Props {
  materialId: string;
  rowId: string;
  canEdit: boolean;
  onOpen: (rowId: string | null) => void;
  onEdit: (row: PositionRow) => void;
  onAlternativeCs: (row: PositionRow) => void;
}

/** A row of the CONFUNFIS (E13), in the docked detail panel (E15): its fields, the article
 *  (to its card), the CS and the rows hanging from it (each opens its own
 *  card), the total in the CUF with how it comes out, its observations and
 *  history; and, with confunfis.editar, edit, duplicate as alternative,
 *  add an alternative CS and remove. */
export function RowSheet({ materialId, rowId, canEdit, onOpen, onEdit, onAlternativeCs }: Props): React.JSX.Element {
  const { t, i18n } = useTranslation();
  // Once its removal is confirmed the card stops reading its row: closing
  // may take a render, and a read of a removed row is a 404.
  const [gone, setGone] = useState(false);
  const detail = useConfunfisRow(materialId, gone ? null : rowId);
  const remove = useDeleteRow(materialId);
  const duplicate = useDuplicateAlternative(materialId);
  const [removing, setRemoving] = useState(false);
  // NT §9.1.6: the last AL of a hueco goes back to 00 (offered, on by default).
  const [resetAfter, setResetAfter] = useState(true);
  const reset = useResetAl(materialId);
  const row = detail.data;
  const leavesSingle = Boolean(row && row.hueco_als.length === 2 && row.hueco_als.includes(row.al) && !row.hueco_als.includes('00'));
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  const field = (label: string, value: React.ReactNode) => (
    <div className="grid grid-cols-[9rem_1fr] gap-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value ?? '—'}</dd>
    </div>
  );

  return (
    <DetailPanel
      title={row ? `${positionOf(row)} · ${row.article_name ?? t('confunfis.noName')}` : t('confunfis.card.title')}
      description={row?.sns_name ?? ''} onClose={() => onOpen(null)} testId="row-sheet"
    >
        {!row ? (
          <Skeleton className="m-4 h-96" />
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-6">
            <div className="flex flex-wrap gap-1">
              {row.alternative ? <Badge variant="outline">{t('confunfis.badges.alternative')}</Badge> : null}
              {row.cs_alternative ? <Badge variant="outline">{t('confunfis.badges.csAlternative')}</Badge> : null}
              {row.ct_sigle === 'S' ? <Badge variant="secondary">{t('confunfis.badges.ctSigle')}</Badge> : null}
              {row.is_mounted ? <Badge variant="outline">{t('confunfis.badges.mounted')}</Badge> : null}
              {row.extra_function_count ? <Badge variant="outline">{t('confunfis.badges.multifunction', { count: row.extra_function_count })}</Badge> : null}
              <ObservationBadges row={row} />
            </div>
            {canEdit ? (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => onEdit(row)} data-testid="row-edit">{t('confunfis.card.edit')}</Button>
                <Button
                  size="sm" variant="outline" disabled={duplicate.isPending} data-testid="row-duplicate-alternative"
                  onClick={() => duplicate.mutate(row, { onSuccess: (created) => onOpen(created.id) })}
                >
                  {t('confunfis.card.duplicateAlternative')}
                </Button>
                <Button size="sm" variant="outline" onClick={() => onAlternativeCs(row)} data-testid="row-alternative-cs">{t('confunfis.card.alternativeCs')}</Button>
                {row.observation_codes.includes('OF-012') ? (
                  <Button size="sm" variant="outline" disabled={reset.isPending} onClick={() => reset.mutate(row)} data-testid="row-reset-al">{t('confunfis.card.resetAl')}</Button>
                ) : null}
                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setRemoving(true)} data-testid="row-delete">{t('confunfis.card.remove')}</Button>
              </div>
            ) : null}
            <dl className="flex flex-col gap-1" data-testid="row-fields">
              {field(t('confunfis.fields.qty'), row.qty)}
              {field(t('confunfis.fields.total'), <span data-testid="row-total">{row.total ?? t('confunfis.card.noTotal')}</span>)}
              {row.chains.length ? field(t('confunfis.card.calculation'), (
                <ul data-testid="row-calculation">{row.chains.map((c, i) => <li key={i} className="font-mono text-xs">{chainText(c, row.chains.length === 1 ? row.total : null)}</li>)}</ul>
              )) : null}
              {field(t('confunfis.fields.article_name'), row.article_name)}
              {field(t('confunfis.fields.function_text'), row.function_text)}
              {field(t('confunfis.fields.ct_sigle'), row.ct_sigle)}
              {field(t('confunfis.fields.source'), t(`confunfis.sources.${row.source}`))}
            </dl>
            <Separator />
            <section className="flex flex-col gap-1 text-sm" data-testid="row-article">
              <h3 className="font-medium">{t('confunfis.card.article')}</h3>
              {row.article ? (
                <>
                  <Link to={`${ARTICLES_PATH}/${row.article.id}`} className="text-link underline-offset-2 hover:underline">{row.article.nombre}</Link>
                  <span className="font-mono text-xs text-muted-foreground">
                    {[row.article.noc ?? t('confunfis.card.noNoc'), row.article.pn && `${row.article.pn} / ${row.article.ncage ?? ''}`].filter(Boolean).join(' · ')}
                  </span>
                  {row.article.origin === 'confunfis' ? <Badge variant="outline" className="self-start border-warning text-warning">{t('confunfis.card.provisional')}</Badge> : null}
                </>
              ) : <span className="text-muted-foreground">{t('confunfis.card.noArticle')}</span>}
              {row.mounted ? (
                <Link to={`/materiales/${row.mounted.id}/confunfis`} className="text-link underline-offset-2 hover:underline" data-testid="row-mounted-link">
                  {t('confunfis.card.mountedLink', { name: row.mounted.name })}
                </Link>
              ) : null}
            </section>
            <section className="flex flex-col gap-1 text-sm">
              <h3 className="font-medium">{t('confunfis.card.cs')}</h3>
              {row.parents.length ? row.parents.map((p) => <RowLink key={p.id} row={p} onOpen={onOpen} />) : (
                <span className="font-mono text-xs">{row.orphan ? t(`confunfis.card.orphan.${row.orphan}`, { cs: csOf(row) ?? '' }) : csOf(row) ?? t('confunfis.theCuf')}</span>
              )}
            </section>
            <section className="flex flex-col gap-1 text-sm" data-testid="row-children">
              <h3 className="font-medium">{t('confunfis.card.children', { count: row.children.length })}</h3>
              {row.children.map((c) => <RowLink key={c.id} row={c} onOpen={onOpen} />)}
            </section>
            <Separator />
            <PartsSection row={row} />
            <ExtraFunctionsSection materialId={materialId} row={row} canEdit={canEdit} />
            <IncompatibilitiesSection materialId={materialId} row={row} canEdit={canEdit} onOpen={onOpen} />
            <Separator />
            {row.observations.length ? (
              <section className="flex flex-col gap-1 text-sm" data-testid="row-observations">
                <h3 className="font-medium">{t('confunfis.card.observations')}</h3>
                <ul className="flex flex-col gap-1">
                  {row.observations.map((o, i) => <li key={`${o.code}-${i}`}><Badge variant="outline" className="mr-2">{o.code}</Badge>{observationText(t, o)}</li>)}
                </ul>
              </section>
            ) : null}
            <section className="flex flex-col gap-1 text-sm">
              <h3 className="font-medium">{t('confunfis.card.history')}</h3>
              <ul className="flex flex-col gap-1">
                {row.history.map((h) => (
                  <li key={h.id}>
                    {t(`audit.actions.${h.action}`)}
                    <span className="block text-xs text-muted-foreground">{when(h.at)} · {h.user ?? t('articles.byScript')}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      {row ? (
        <ConfirmDialog
          open={removing}
          onOpenChange={setRemoving}
          title={t('confunfis.card.removeTitle', { position: positionOf(row) })}
          description={
            row.extra_function_count || row.incompatibility_count
              ? `${t('confunfis.card.removeHint')} ${t('confunfis.card.removeWithExtras', { extras: row.extra_function_count, incompatibilities: row.incompatibility_count })}`
              : t('confunfis.card.removeHint')
          }
          confirmLabel={t('confunfis.card.remove')}
          onConfirm={() => { setGone(true); onOpen(null); remove.mutate({ row, resetAl: leavesSingle && resetAfter }); }}
        >
          {leavesSingle ? (
            <div className="flex items-center gap-2 text-sm">
              <Checkbox id="reset-al" checked={resetAfter} onCheckedChange={(c) => setResetAfter(c === true)} data-testid="row-delete-reset-al" />
              <Label htmlFor="reset-al">{t('confunfis.card.resetAfterRemove')}</Label>
            </div>
          ) : null}
        </ConfirmDialog>
      ) : null}
    </DetailPanel>
  );
}
