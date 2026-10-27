// Baselines y cambios (E17): the CUF's baselines as a timeline (vN, state,
// author, reviewer, its validation) with what each state allows -- create,
// withdraw, approve, reject with a comment --, the comparison between two
// baselines or one and the CONFUNFIS as it is now (exportable to Excel),
// and the change authorizations: request, approve or reject, close, and
// the changes made under each. The tab lives in the URL (?tab), nothing in
// the browser (HR1). The server decides every step (four eyes included);
// the page only hides what the user may not do.
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useAuthorizationChanges,
  useAuthorizations,
  useAuthorizationStep,
  useBaselines,
  useBaselineStep,
  useConfigurationState,
  useCreateBaseline,
  useDiff,
  useRequestAuthorization,
} from '@/hooks/useBaselines';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { useReferenceValues } from '@/hooks/useReferenceTables';
import { useMe } from '@/hooks/useSession';
import { useValidation } from '@/hooks/useValidation';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { exportDiff } from '@/services/baselinesApi';
import { CURRENT, type Baseline, type ChangeAuthorization, type DiffEntry } from '@/types/baselines';

const TABS = ['baselines', 'comparar', 'autorizaciones'] as const;
type Tab = (typeof TABS)[number];
const KIND_TABLE = 'TIPO_AUTORIZACION';

const BASELINE_BADGE: Record<Baseline['state'], 'default' | 'secondary' | 'outline' | 'info' | 'warning'> = {
  en_revision: 'warning',
  revisada: 'info',
  rechazada: 'outline',
  retirada: 'secondary',
};
const AUTHORIZATION_BADGE: Record<ChangeAuthorization['state'], 'default' | 'secondary' | 'outline' | 'info' | 'warning'> = {
  solicitada: 'warning',
  aprobada: 'info',
  rechazada: 'outline',
  cerrada: 'secondary',
};

function useWhen(): (iso: string | null) => string {
  const { i18n } = useTranslation();
  return (iso) => (iso ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso)) : '');
}

/** A comment to approve (optional) or to reject (required). */
function CommentDialog({ title, description, required, confirm, onClose, onConfirm, testid }: {
  title: string; description: string; required: boolean; confirm: string; onClose: () => void; onConfirm: (comment: string | null) => void; testid: string;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [comment, setComment] = useState('');
  const ok = !required || comment.trim().length > 0;
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent data-testid={testid}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1">
          <Label htmlFor={`${testid}-comment`}>{required ? t('baselines.comment.required') : t('baselines.comment.optional')}</Label>
          <Input id={`${testid}-comment`} value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} data-testid={`${testid}-comment`} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button disabled={!ok} onClick={() => onConfirm(comment.trim() || null)} data-testid={`${testid}-confirm`}>{confirm}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BaselinesTab({ materialId, onCompare }: { materialId: string; onCompare: (b: Baseline) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const material = useMaterialOfPage();
  const me = useMe();
  const when = useWhen();
  const list = useBaselines(materialId);
  const validation = useValidation(materialId);
  const create = useCreateBaseline(materialId);
  const step = useBaselineStep(materialId);
  const [reviewing, setReviewing] = useState<{ baseline: Baseline; approve: boolean } | null>(null);
  const canCreate = material.permissions.includes('baseline.crear');
  const canReview = material.permissions.includes('baseline.revisar');
  const isAdmin = Boolean(me.data?.is_admin);
  const inReview = (list.data ?? []).some((b) => b.state === 'en_revision');
  const v = validation.data;
  // Why not now (the server checks it again): one in review, no up-to-date validation, blocking findings.
  const why = inReview
    ? t('baselines.create.inReview')
    : !v || v.state === 'none'
      ? t('baselines.create.notValidated')
      : v.outdated
        ? t('baselines.create.outdated')
        : v.blocking > 0
          ? t('baselines.create.blocking', { count: v.blocking })
          : null;

  return (
    <div className="flex flex-col gap-4">
      {canCreate ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={Boolean(why) || create.isPending} onClick={() => create.mutate()} data-testid="baseline-create">
            {t('baselines.create.button')}
          </Button>
          {why ? (
            <p className="text-sm text-muted-foreground" data-testid="baseline-create-why">
              {why}{' '}
              <Link to={`/materiales/${materialId}/validacion`} className="text-link underline-offset-2 hover:underline">{t('baselines.create.toValidation')}</Link>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">{t('baselines.create.hint')}</p>
          )}
        </div>
      ) : null}
      {list.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {list.data && list.data.length === 0 ? <p className="text-muted-foreground" data-testid="baselines-empty">{t('baselines.empty')}</p> : null}
      <ol className="flex flex-col gap-3 border-l-2 border-border pl-4" data-testid="baselines-timeline">
        {(list.data ?? []).map((b) => {
          const own = b.created_by === me.data?.id;
          return (
            <li key={b.id} data-testid={`baseline-v${b.number}`} data-state={b.state}>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                    {t('baselines.version', { number: b.number })}
                    <Badge variant={BASELINE_BADGE[b.state]} data-testid={`baseline-v${b.number}-state`}>{t(`baselines.states.${b.state}`)}</Badge>
                    {b.validation ? (
                      <Link to={`/materiales/${materialId}/validacion`} className="text-link text-sm font-normal underline-offset-2 hover:underline">
                        {t(`baselines.light.${b.validation.state}`, { blocking: b.validation.blocking, warnings: b.validation.warnings })}
                      </Link>
                    ) : null}
                  </CardTitle>
                  <CardDescription>
                    {t('baselines.createdBy', { by: b.created_by_name ?? t('articles.byScript'), at: when(b.created_at) })} · {t('baselines.rows', { count: b.rows })}
                    {b.reviewed_at ? ` · ${t(`baselines.reviewedBy.${b.state === 'rechazada' ? 'rejected' : b.state === 'retirada' ? 'withdrawn' : 'approved'}`, { by: b.reviewed_by_name ?? '', at: when(b.reviewed_at) })}` : ''}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm">
                  {b.review_comment ? <p data-testid={`baseline-v${b.number}-comment`}>{t('baselines.comment.shown', { text: b.review_comment })}</p> : null}
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => onCompare(b)} data-testid={`baseline-v${b.number}-compare`}>{t('baselines.compare.withCurrent')}</Button>
                    {b.state === 'en_revision' && canCreate && (own || isAdmin) ? (
                      <Button variant="outline" size="sm" onClick={() => step.mutate({ baseline: b, action: 'withdraw' })} data-testid={`baseline-v${b.number}-withdraw`}>
                        {t('baselines.actions.withdraw')}
                      </Button>
                    ) : null}
                    {b.state === 'en_revision' && canReview && !own ? (
                      <>
                        <Button size="sm" onClick={() => setReviewing({ baseline: b, approve: true })} data-testid={`baseline-v${b.number}-approve`}>{t('baselines.actions.approve')}</Button>
                        <Button variant="outline" size="sm" onClick={() => setReviewing({ baseline: b, approve: false })} data-testid={`baseline-v${b.number}-reject`}>{t('baselines.actions.reject')}</Button>
                      </>
                    ) : null}
                    {b.state === 'en_revision' && canReview && own ? <span className="text-xs text-muted-foreground">{t('baselines.fourEyes')}</span> : null}
                  </div>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ol>
      {reviewing ? (
        <CommentDialog
          testid="baseline-review"
          title={t(reviewing.approve ? 'baselines.review.approveTitle' : 'baselines.review.rejectTitle', { number: reviewing.baseline.number })}
          description={t(reviewing.approve ? 'baselines.review.approveHint' : 'baselines.review.rejectHint')}
          required={!reviewing.approve}
          confirm={t(reviewing.approve ? 'baselines.actions.approve' : 'baselines.actions.reject')}
          onClose={() => setReviewing(null)}
          onConfirm={(comment) => {
            step.mutate({ baseline: reviewing.baseline, action: reviewing.approve ? 'approve' : 'reject', comment });
            setReviewing(null);
          }}
        />
      ) : null}
    </div>
  );
}

function DiffTable({ entries }: { entries: DiffEntry[] }): React.JSX.Element {
  const { t } = useTranslation();
  if (entries.length === 0) return <p className="text-muted-foreground" data-testid="diff-empty">{t('baselines.compare.none')}</p>;
  return (
    <Table data-testid="diff-table">
      <TableHeader>
        <TableRow>
          {(['entity', 'label', 'change', 'field', 'before', 'after', 'authorization'] as const).map((c) => (
            <TableHead key={c}>{t(`baselines.diffColumns.${c}`)}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.flatMap((e) => {
          const fields = e.fields.length ? e.fields : [null];
          return fields.map((f, i) => (
            <TableRow key={`${e.entity}-${e.id}-${f?.field ?? ''}`} data-testid="diff-row" data-entity={e.entity} data-change={e.change}>
              {i === 0 ? (
                <>
                  <TableCell rowSpan={fields.length}>{t(`baselines.entities.${e.entity}`)}</TableCell>
                  <TableCell rowSpan={fields.length} className="font-mono text-xs">{e.label}</TableCell>
                  <TableCell rowSpan={fields.length}>
                    <Badge variant={e.change === 'modified' ? 'warning' : e.change === 'added' ? 'info' : 'outline'}>{t(`baselines.changes.${e.change}`)}</Badge>
                  </TableCell>
                </>
              ) : null}
              <TableCell>{f?.label ?? ''}</TableCell>
              <TableCell className="text-muted-foreground line-through decoration-destructive/60">{f?.before ?? ''}</TableCell>
              <TableCell className="font-medium" data-testid="diff-after">{f?.after ?? ''}</TableCell>
              {i === 0 ? (
                <TableCell rowSpan={fields.length} className="font-mono text-xs" data-testid="diff-authorization">
                  {e.authorizations.map((a) => a.code).join(', ') || t('baselines.compare.noAuthorization')}
                </TableCell>
              ) : null}
            </TableRow>
          ));
        })}
      </TableBody>
    </Table>
  );
}

function CompareTab({ materialId, before, after, onChange }: { materialId: string; before: string | null; after: string; onChange: (before: string | null, after: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const list = useBaselines(materialId);
  const all = list.data ?? [];
  const chosen = before ?? all.find((b) => b.state === 'revisada')?.id ?? all[0]?.id ?? null;
  const diff = useDiff(materialId, chosen, after);
  const download = () => {
    if (!chosen) return;
    exportDiff(materialId, chosen, after)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? 'COMPARACION.xlsx'))
      .catch((error: unknown) => notifyError(error, t));
  };
  if (list.data && all.length === 0) return <p className="text-muted-foreground">{t('baselines.empty')}</p>;
  const label = (b: Baseline) => `${t('baselines.version', { number: b.number })} · ${t(`baselines.states.${b.state}`)}`;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label>{t('baselines.compare.before')}</Label>
          <Select value={chosen ?? undefined} onValueChange={(v) => onChange(v, after)}>
            <SelectTrigger className="w-56" data-testid="diff-before"><SelectValue /></SelectTrigger>
            <SelectContent>
              {all.map((b) => <SelectItem key={b.id} value={b.id}>{label(b)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label>{t('baselines.compare.after')}</Label>
          <Select value={after} onValueChange={(v) => onChange(chosen, v)}>
            <SelectTrigger className="w-56" data-testid="diff-after-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={CURRENT}>{t('baselines.compare.current')}</SelectItem>
              {all.filter((b) => b.id !== chosen).map((b) => <SelectItem key={b.id} value={b.id}>{label(b)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" disabled={!diff.data} onClick={download} data-testid="diff-export">{t('baselines.compare.export')}</Button>
      </div>
      {diff.data ? (
        <>
          <p className="text-sm text-muted-foreground" data-testid="diff-summary">
            {t('baselines.compare.summary', { count: diff.data.entries.length, before: diff.data.before, after: diff.data.after })}
          </p>
          <DiffTable entries={diff.data.entries} />
        </>
      ) : chosen ? <Skeleton className="h-40 w-full" /> : null}
    </div>
  );
}

function RequestDialog({ materialId, onClose }: { materialId: string; onClose: () => void }): React.JSX.Element {
  const { t } = useTranslation();
  const kinds = useReferenceValues(KIND_TABLE);
  const request = useRequestAuthorization(materialId);
  const [kind, setKind] = useState('');
  const [description, setDescription] = useState('');
  const [reason, setReason] = useState('');
  const ok = kind && description.trim() && reason.trim();
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent data-testid="authorization-request">
        <DialogHeader>
          <DialogTitle>{t('baselines.authorizations.requestTitle')}</DialogTitle>
          <DialogDescription>{t('baselines.authorizations.requestHint')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>{t('baselines.authorizations.kind')}</Label>
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger data-testid="authorization-kind"><SelectValue placeholder={t('baselines.authorizations.kindPlaceholder')} /></SelectTrigger>
              <SelectContent>
                {(kinds.data ?? []).filter((v) => v.is_active).map((v) => (
                  <SelectItem key={v.code} value={v.code} data-testid={`authorization-kind-${v.code}`}>{v.description}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="authorization-description">{t('baselines.authorizations.description')}</Label>
            <Input id="authorization-description" value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} data-testid="authorization-description" />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="authorization-reason">{t('baselines.authorizations.reason')}</Label>
            <Input id="authorization-reason" value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} data-testid="authorization-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button
            disabled={!ok || request.isPending}
            onClick={() => request.mutate({ kind, description: description.trim(), reason: reason.trim() }, { onSuccess: onClose })}
            data-testid="authorization-request-save"
          >
            {t('baselines.authorizations.request')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AuthorizationChanges({ materialId, id }: { materialId: string; id: string }): React.JSX.Element {
  const { t } = useTranslation();
  const when = useWhen();
  const changes = useAuthorizationChanges(materialId, id);
  if (!changes.data) return <Skeleton className="h-8 w-full" />;
  if (changes.data.length === 0) return <p className="text-muted-foreground">{t('baselines.authorizations.noChanges')}</p>;
  return (
    <ul className="flex flex-col gap-1" data-testid="authorization-changes">
      {changes.data.map((c, i) => (
        <li key={`${c.entity_id}-${i}`}>
          <span className="font-mono text-xs">{c.label}</span> · {t(`baselines.authorizations.actions.${c.action}`)}
          <span className="block text-xs text-muted-foreground">{when(c.at)} · {c.by ?? t('articles.byScript')}</span>
        </li>
      ))}
    </ul>
  );
}

function AuthorizationsTab({ materialId }: { materialId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const material = useMaterialOfPage();
  const me = useMe();
  const when = useWhen();
  const list = useAuthorizations(materialId);
  const kinds = useReferenceValues(KIND_TABLE);
  const step = useAuthorizationStep(materialId);
  const [asking, setAsking] = useState(false);
  const [deciding, setDeciding] = useState<{ authorization: ChangeAuthorization; approve: boolean } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const canRequest = material.permissions.includes('autorizacion.solicitar');
  const canDecide = material.permissions.includes('autorizacion.aprobar');
  const isAdmin = Boolean(me.data?.is_admin);
  const kindName = useMemo(() => Object.fromEntries((kinds.data ?? []).map((v) => [v.code, v.description])), [kinds.data]);
  return (
    <div className="flex flex-col gap-4">
      {canRequest ? (
        <div>
          <Button onClick={() => setAsking(true)} data-testid="authorization-new">{t('baselines.authorizations.new')}</Button>
        </div>
      ) : null}
      {list.data && list.data.length === 0 ? <p className="text-muted-foreground">{t('baselines.authorizations.empty')}</p> : null}
      {list.data && list.data.length > 0 ? (
        <Table data-testid="authorizations-table">
          <TableHeader>
            <TableRow>
              <TableHead>{t('baselines.authorizations.code')}</TableHead>
              <TableHead>{t('baselines.authorizations.kind')}</TableHead>
              <TableHead>{t('baselines.authorizations.description')}</TableHead>
              <TableHead>{t('baselines.authorizations.state')}</TableHead>
              <TableHead>{t('baselines.authorizations.requested')}</TableHead>
              <TableHead>{t('baselines.authorizations.changes')}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.data.flatMap((a) => {
              const own = a.requested_by === me.data?.id;
              const row = (
                <TableRow key={a.id} data-testid={`authorization-${a.code}`} data-state={a.state}>
                  <TableCell className="font-mono text-xs">{a.code}</TableCell>
                  <TableCell>{kindName[a.kind] ?? a.kind}</TableCell>
                  <TableCell>
                    {a.description}
                    <span className="block text-xs text-muted-foreground">{t('baselines.authorizations.because', { reason: a.reason })}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={AUTHORIZATION_BADGE[a.state]} data-testid={`authorization-${a.code}-state`}>{t(`baselines.authorizations.states.${a.state}`)}</Badge>
                    {a.closed_in_baseline ? <span className="block text-xs text-muted-foreground">{t('baselines.authorizations.closedIn', { number: a.closed_in_baseline })}</span> : null}
                    {a.decision_comment ? <span className="block text-xs text-muted-foreground">{a.decision_comment}</span> : null}
                  </TableCell>
                  <TableCell className="text-xs">
                    {a.requested_by_name ?? t('articles.byScript')} · {when(a.requested_at)}
                    {a.decided_by_name ? <span className="block text-muted-foreground">{t('baselines.authorizations.decidedBy', { by: a.decided_by_name, at: when(a.decided_at) })}</span> : null}
                  </TableCell>
                  <TableCell>
                    <Button variant="link" className="h-auto p-0 text-link" onClick={() => setOpen(open === a.id ? null : a.id)} data-testid={`authorization-${a.code}-changes`}>
                      {t('baselines.authorizations.changesCount', { count: a.changes })}
                    </Button>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {a.state === 'solicitada' && canDecide && !own ? (
                      <span className="flex gap-2">
                        <Button size="sm" onClick={() => setDeciding({ authorization: a, approve: true })} data-testid={`authorization-${a.code}-approve`}>{t('baselines.actions.approve')}</Button>
                        <Button size="sm" variant="outline" onClick={() => setDeciding({ authorization: a, approve: false })} data-testid={`authorization-${a.code}-reject`}>{t('baselines.actions.reject')}</Button>
                      </span>
                    ) : null}
                    {a.state === 'solicitada' && canDecide && own ? <span className="text-xs text-muted-foreground">{t('baselines.authorizations.notOwn')}</span> : null}
                    {a.state === 'aprobada' && (own || isAdmin) ? (
                      <Button size="sm" variant="outline" onClick={() => step.mutate({ authorization: a, action: 'close' })} data-testid={`authorization-${a.code}-close`}>
                        {t('baselines.authorizations.close')}
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
              return open === a.id
                ? [row, (
                  <TableRow key={`${a.id}-changes`}>
                    <TableCell colSpan={7} className="bg-muted/40 text-sm"><AuthorizationChanges materialId={materialId} id={a.id} /></TableCell>
                  </TableRow>
                )]
                : [row];
            })}
          </TableBody>
        </Table>
      ) : null}
      {asking ? <RequestDialog materialId={materialId} onClose={() => setAsking(false)} /> : null}
      {deciding ? (
        <CommentDialog
          testid="authorization-decide"
          title={t(deciding.approve ? 'baselines.authorizations.approveTitle' : 'baselines.authorizations.rejectTitle', { code: deciding.authorization.code })}
          description={deciding.authorization.description}
          required={!deciding.approve}
          confirm={t(deciding.approve ? 'baselines.actions.approve' : 'baselines.actions.reject')}
          onClose={() => setDeciding(null)}
          onConfirm={(comment) => {
            step.mutate({ authorization: deciding.authorization, action: deciding.approve ? 'approve' : 'reject', comment });
            setDeciding(null);
          }}
        />
      ) : null}
    </div>
  );
}

export function BaselinesPage(): React.JSX.Element {
  const { t } = useTranslation();
  const material = useMaterialOfPage();
  const [params, setParams] = useSearchParams();
  const state = useConfigurationState(material.id);
  const tab: Tab = TABS.find((x) => x === params.get('tab')) ?? 'baselines';
  const go = (next: Record<string, string | null>) => {
    const out = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) out.set(k, v);
      else out.delete(k);
    }
    setParams(out);
  };
  const title = t('baselines.title');
  const s = state.data;
  return (
    <div className="flex flex-col gap-6" data-testid="baselines-page">
      <PageHeader crumbs={[{ label: material.name, to: `/materiales/${material.id}` }, { label: title }]} title={title} />
      {s ? (
        <Alert data-testid="baselines-state">
          <AlertDescription>
            {s.in_review
              ? t('baselines.band.locked', { number: s.in_review.number })
              : s.reviewed
                ? `${t('baselines.band.reviewed', { number: s.reviewed.number })} · ${t('baselines.band.changesSince', { count: s.changes_since, number: s.reviewed.number })}`
                : t('baselines.band.none')}
            {s.open_authorizations ? ` · ${t('baselines.band.openAuthorizations', { count: s.open_authorizations })}` : ''}
          </AlertDescription>
        </Alert>
      ) : null}
      <Tabs value={tab} onValueChange={(v) => go({ tab: v === 'baselines' ? null : v })}>
        <TabsList>
          {TABS.map((name) => (
            <TabsTrigger key={name} value={name} data-testid={`baselines-tab-${name}`}>{t(`baselines.tabs.${name}`)}</TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="baselines">
          <BaselinesTab materialId={material.id} onCompare={(b) => go({ tab: 'comparar', antes: b.id, despues: CURRENT })} />
        </TabsContent>
        <TabsContent value="comparar">
          <CompareTab
            materialId={material.id} before={params.get('antes')} after={params.get('despues') ?? CURRENT}
            onChange={(before, after) => go({ antes: before, despues: after })}
          />
        </TabsContent>
        <TabsContent value="autorizaciones">
          <AuthorizationsTab materialId={material.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
