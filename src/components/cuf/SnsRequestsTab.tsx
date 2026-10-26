import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { useMe } from '@/hooks/useSession';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { describeApiError } from '@/services/apiErrors';
import { annulSnsRequest, createSnsRequest, discardSnsRequest, exportSnsRequests, fetchSnsRequests, resolveSnsRequest, submitSnsRequest, updateSnsRequest } from '@/services/cufApi';
import type { SnsRequest, SnsRequestFields, SnsRequestState } from '@/types/cuf';

const EMPTY: SnsRequestFields = { proposed_sns: null, parent_sns: null, name: '', function: '', justification: '' };
const STATE_VARIANT: Record<SnsRequestState, 'outline' | 'secondary' | 'default' | 'destructive'> = {
  borrador: 'outline',
  enviada: 'secondary',
  aceptada: 'default',
  rechazada: 'destructive',
};

function RequestForm({ open, initial, onOpenChange, onSave, error, saving }: {
  open: boolean;
  initial: SnsRequestFields;
  onOpenChange: (open: boolean) => void;
  onSave: (fields: SnsRequestFields) => void;
  error: unknown;
  saving: boolean;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [fields, setFields] = useState(initial);
  const set = (patch: Partial<SnsRequestFields>) => setFields((f) => ({ ...f, ...patch }));
  const code = (v: string) => v.replace(/\s+/g, '').toUpperCase() || null;
  const sns = /^([A-Z0-9]{6})?$/;
  const wrong = !sns.test(fields.proposed_sns ?? '') || !sns.test(fields.parent_sns ?? '');
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="sns-request-form">
        <DialogHeader>
          <DialogTitle>{t('cuf.requests.formTitle')}</DialogTitle>
          <DialogDescription>{t('cuf.requests.formHint')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="req-sns">{t('cuf.requests.proposedSns')}</Label>
              <Input id="req-sns" className="font-mono" value={fields.proposed_sns ?? ''} onChange={(e) => set({ proposed_sns: code(e.target.value) })} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="req-parent">{t('cuf.requests.parentSns')}</Label>
              <Input id="req-parent" className="font-mono" value={fields.parent_sns ?? ''} onChange={(e) => set({ parent_sns: code(e.target.value) })} />
            </div>
          </div>
          {wrong ? <p className="text-sm text-destructive">{t('validation.sns')}</p> : null}
          <div className="flex flex-col gap-2">
            <Label htmlFor="req-name">{t('cuf.requests.name')}</Label>
            <Input id="req-name" value={fields.name} onChange={(e) => set({ name: e.target.value })} maxLength={300} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="req-function">{t('cuf.requests.function')}</Label>
            <Input id="req-function" value={fields.function} onChange={(e) => set({ function: e.target.value })} maxLength={4000} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="req-justification">{t('cuf.requests.justification')}</Label>
            <Input id="req-justification" value={fields.justification} onChange={(e) => set({ justification: e.target.value })} maxLength={4000} />
          </div>
          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {describeApiError(error, t).message}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('actions.cancel')}
          </Button>
          <Button disabled={wrong || !fields.name.trim() || !fields.justification.trim() || saving} onClick={() => onSave(fields)} data-testid="sns-request-save">
            {t('actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Requests for a new SNS (NT §9.1.1): drafted and sent by whoever edits
 *  the material, accepted or rejected by an admin with an answer, and the
 *  sent ones exported to send them to JIMALE. A draft is discarded by its
 *  author or whoever edits the material; once sent, only an admin annuls it,
 *  with a reason ("Mostrar anuladas" brings those back). Steps on an existing
 *  request are optimistic (HR20); a new one is not (its id comes from the server). */
export function SnsRequestsTab({ materialId, canEdit, isAdmin }: { materialId: string; canEdit: boolean; isAdmin: boolean }): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const me = useMe();
  const [showAnnulled, setShowAnnulled] = useState(false);
  const key = ['materials', materialId, 'sns-requests', showAnnulled] as const;
  const list = useQuery({ queryKey: key, queryFn: () => fetchSnsRequests(materialId, showAnnulled) });
  const [annulling, setAnnulling] = useState<SnsRequest | null>(null);
  const [reason, setReason] = useState('');
  const [form, setForm] = useState<{ request: SnsRequest | null } | null>(null);
  const [discarding, setDiscarding] = useState<SnsRequest | null>(null);
  const [resolving, setResolving] = useState<{ request: SnsRequest; decision: 'aceptada' | 'rechazada' } | null>(null);
  const [response, setResponse] = useState('');
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['materials', materialId, 'sns-requests'] });
  const save = useMutation({
    mutationFn: (fields: SnsRequestFields) =>
      form?.request ? updateSnsRequest(materialId, form.request.id, form.request.version, fields) : createSnsRequest(materialId, fields),
    onSuccess: () => {
      refresh();
      setForm(null);
    },
  });
  const step = useOptimisticMutation<SnsRequest, { request: SnsRequest; to: SnsRequestState; response?: string }, SnsRequest>({
    queryKey: key,
    mutationFn: ({ request, to, response: answer }) =>
      to === 'enviada'
        ? submitSnsRequest(materialId, request.id, request.version)
        : resolveSnsRequest(materialId, request.id, request.version, to as 'aceptada' | 'rechazada', answer ?? ''),
    apply: (rows, { request, to, response: answer }) => rows.map((r) => (r.id === request.id ? { ...r, state: to, response: answer ?? r.response } : r)),
    settle: (rows, saved) => rows.map((r) => (r.id === saved.id ? saved : r)),
  });
  const discard = useOptimisticMutation<SnsRequest, SnsRequest, void>({
    queryKey: key,
    mutationFn: (r) => discardSnsRequest(materialId, r.id, r.version),
    apply: (rows, r) => rows.filter((x) => x.id !== r.id),
  });
  const annul = useOptimisticMutation<SnsRequest, { request: SnsRequest; reason: string }, void>({
    queryKey: key,
    mutationFn: ({ request, reason: why }) => annulSnsRequest(materialId, request.id, request.version, why),
    // Out of the list, or marked annulled when those are shown.
    apply: (rows, { request, reason: why }) =>
      showAnnulled
        ? rows.map((r) => (r.id === request.id ? { ...r, annulled_at: new Date().toISOString(), annul_reason: why } : r))
        : rows.filter((r) => r.id !== request.id),
    invalidate: [['materials', materialId, 'sns-requests']],
  });
  const canDiscard = (r: SnsRequest) => r.state === 'borrador' && (canEdit || (me.data !== undefined && r.created_by_id === me.data.id));
  const when = (iso: string | null) => (iso ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short' }).format(new Date(iso)) : t('material.empty'));
  const doExport = () =>
    exportSnsRequests(materialId)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? 'SOLICITUDES_SNS.xlsx'))
      .catch((error: unknown) => notifyError(error, t));

  if (!list.data) return <Skeleton className="h-40 w-full" />;
  return (
    <div className="flex flex-col gap-4" data-testid="sns-requests">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-muted-foreground">{t('cuf.requests.hint')}</p>
        <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
          {isAdmin ? (
            <div className="flex items-center gap-2">
              <Switch id="show-annulled" checked={showAnnulled} onCheckedChange={setShowAnnulled} data-testid="sns-requests-show-annulled" />
              <Label htmlFor="show-annulled">{t('cuf.requests.showAnnulled')}</Label>
            </div>
          ) : null}
          <Button variant="outline" onClick={() => void doExport()} data-testid="sns-requests-export">
            {t('cuf.requests.export')}
          </Button>
          {canEdit ? (
            <Button onClick={() => { save.reset(); setForm({ request: null }); }} data-testid="sns-request-new">
              {t('cuf.requests.new')}
            </Button>
          ) : null}
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('cuf.requests.state')}</TableHead>
            <TableHead>{t('cuf.requests.proposedSns')}</TableHead>
            <TableHead>{t('cuf.requests.parentSns')}</TableHead>
            <TableHead>{t('cuf.requests.name')}</TableHead>
            <TableHead>{t('cuf.requests.justification')}</TableHead>
            <TableHead>{t('cuf.requests.dates')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.more')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {list.data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">
                {t('cuf.requests.empty')}
              </TableCell>
            </TableRow>
          ) : (
            list.data.map((r) => (
              <TableRow key={r.id} data-testid={`sns-request-${r.name}`} data-annulled={r.annulled_at ? '' : undefined} className={r.annulled_at ? 'text-muted-foreground' : undefined}>
                <TableCell>
                  <Badge variant={STATE_VARIANT[r.state]} data-testid="sns-request-state">
                    {t(`cuf.requests.states.${r.state}`)}
                  </Badge>
                  {r.annulled_at ? (
                    <Badge variant="outline" className="ml-1 border-destructive text-destructive" data-testid="sns-request-annulled">
                      {t('cuf.requests.annulled')}
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell className="font-mono">{r.proposed_sns ?? t('material.empty')}</TableCell>
                <TableCell className="font-mono">{r.parent_sns ?? t('material.empty')}</TableCell>
                <TableCell className="whitespace-normal">
                  {r.name}
                  {r.function ? <span className="block text-xs text-muted-foreground">{r.function}</span> : null}
                </TableCell>
                <TableCell className="whitespace-normal">
                  {r.justification}
                  {r.response ? <span className="block text-xs text-muted-foreground">{t('cuf.requests.response')}: {r.response}</span> : null}
                  {r.annul_reason ? (
                    <span className="block text-xs text-destructive">
                      {t('cuf.requests.annulledBecause', { reason: r.annul_reason, by: r.annulled_by ?? t('settings.audit.removedUser') })}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="text-xs whitespace-normal">
                  {t('cuf.requests.created', { date: when(r.created_at), by: r.created_by ?? t('settings.audit.removedUser') })}
                  {r.sent_at ? <span className="block">{t('cuf.requests.sent', { date: when(r.sent_at) })}</span> : null}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {canEdit && r.state === 'borrador' ? (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => { save.reset(); setForm({ request: r }); }}>
                        {t('actions.edit')}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => step.mutate({ request: r, to: 'enviada' })} data-testid="sns-request-send">
                        {t('cuf.requests.send')}
                      </Button>
                    </>
                  ) : null}
                  {canDiscard(r) ? (
                    <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDiscarding(r)} data-testid="sns-request-discard">
                      <Trash2 aria-hidden="true" />
                      {t('cuf.requests.discard')}
                    </Button>
                  ) : null}
                  {isAdmin && r.state !== 'borrador' && !r.annulled_at ? (
                    <Button size="sm" variant="ghost" className="text-destructive" onClick={() => { setReason(''); setAnnulling(r); }} data-testid="sns-request-annul">
                      <Ban aria-hidden="true" />
                      {t('cuf.requests.annul')}
                    </Button>
                  ) : null}
                  {isAdmin && r.state === 'enviada' && !r.annulled_at ? (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => { setResponse(''); setResolving({ request: r, decision: 'aceptada' }); }} data-testid="sns-request-accept">
                        {t('cuf.requests.accept')}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setResponse(''); setResolving({ request: r, decision: 'rechazada' }); }} data-testid="sns-request-reject">
                        {t('cuf.requests.reject')}
                      </Button>
                    </>
                  ) : null}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {form ? (
        <RequestForm
          key={form.request?.id ?? 'new'}
          open
          initial={form.request ?? EMPTY}
          onOpenChange={(open) => !open && setForm(null)}
          onSave={(fields) => save.mutate(fields)}
          error={save.error}
          saving={save.isPending}
        />
      ) : null}
      <ConfirmDialog
        open={discarding !== null}
        onOpenChange={(open) => !open && setDiscarding(null)}
        title={t('cuf.requests.discardTitle', { name: discarding?.name ?? '' })}
        description={t('cuf.requests.discardHint')}
        confirmLabel={t('cuf.requests.discard')}
        onConfirm={() => {
          if (discarding) discard.mutate(discarding);
          setDiscarding(null);
        }}
      />
      <Dialog open={annulling !== null} onOpenChange={(open) => !open && setAnnulling(null)}>
        <DialogContent data-testid="sns-request-annul-dialog">
          <DialogHeader>
            <DialogTitle>{t('cuf.requests.annulTitle', { name: annulling?.name ?? '' })}</DialogTitle>
            <DialogDescription>{t('cuf.requests.annulHint')}</DialogDescription>
          </DialogHeader>
          <Label htmlFor="req-annul-reason">{t('cuf.requests.annulReason')}</Label>
          <Input id="req-annul-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={4000} data-testid="sns-request-annul-reason" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAnnulling(null)}>
              {t('actions.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={!reason.trim()}
              onClick={() => {
                if (annulling) annul.mutate({ request: annulling, reason: reason.trim() });
                setAnnulling(null);
              }}
              data-testid="sns-request-annul-confirm"
            >
              {t('cuf.requests.annul')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={resolving !== null} onOpenChange={(open) => !open && setResolving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {resolving?.decision === 'aceptada' ? t('cuf.requests.acceptTitle', { name: resolving.request.name }) : t('cuf.requests.rejectTitle', { name: resolving?.request.name ?? '' })}
            </DialogTitle>
            <DialogDescription>{t('cuf.requests.resolveHint')}</DialogDescription>
          </DialogHeader>
          <Label htmlFor="req-response">{t('cuf.requests.response')}</Label>
          <Input id="req-response" value={response} onChange={(e) => setResponse(e.target.value)} maxLength={4000} data-testid="sns-request-response" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setResolving(null)}>
              {t('actions.cancel')}
            </Button>
            <Button
              disabled={!response.trim()}
              onClick={() => {
                if (resolving) step.mutate({ request: resolving.request, to: resolving.decision, response: response.trim() });
                setResolving(null);
              }}
              data-testid="sns-request-resolve"
            >
              {t('actions.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
