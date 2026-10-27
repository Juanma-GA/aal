// Baselines and change authorizations of a CUF (E17). Creating a baseline
// or requesting an authorization is not optimistic: its number (vN,
// AC-…-NNN) and its snapshot are the server's (as creating a material,
// HR20). Withdrawing, reviewing, deciding and closing are: the new state is
// shown at once and undone if the server refuses.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { notifyError } from '@/lib/notify';
import {
  closeAuthorization,
  createBaseline,
  decideAuthorization,
  fetchAuthorizationChanges,
  fetchAuthorizations,
  fetchBaselines,
  fetchConfigurationState,
  fetchDiff,
  requestAuthorization,
  reviewBaseline,
  withdrawBaseline,
} from '@/services/baselinesApi';
import type { Gate } from '@/components/layout/GatedButton';
import { useUiStore } from '@/stores/uiStore';
import type { Baseline, ChangeAuthorization } from '@/types/baselines';

export const baselinesKey = (materialId: string) => ['baselines', materialId] as const;
const listKey = (materialId: string) => [...baselinesKey(materialId), 'list'] as const;
const stateKey = (materialId: string) => [...baselinesKey(materialId), 'state'] as const;
const authorizationsKey = (materialId: string) => [...baselinesKey(materialId), 'authorizations'] as const;

/** Everything the CUF's change control touches: its baselines, the CONFUNFIS (editable or not), its validation. */
const touched = (materialId: string) => [baselinesKey(materialId), ['confunfis', materialId], ['validation', materialId]];

export function useBaselines(materialId: string) {
  return useQuery({ queryKey: listKey(materialId), queryFn: () => fetchBaselines(materialId) });
}

/** The CUF's configuration state: the CONFUNFIS band and the Panel. */
export function useConfigurationState(materialId: string, enabled = true) {
  return useQuery({ queryKey: stateKey(materialId), queryFn: () => fetchConfigurationState(materialId), enabled, refetchOnWindowFocus: true });
}

export function useAuthorizations(materialId: string) {
  return useQuery({ queryKey: authorizationsKey(materialId), queryFn: () => fetchAuthorizations(materialId) });
}

export function useAuthorizationChanges(materialId: string, id: string | null) {
  return useQuery({
    queryKey: [...authorizationsKey(materialId), id, 'changes'],
    queryFn: () => fetchAuthorizationChanges(materialId, id ?? ''),
    enabled: Boolean(id),
  });
}

export function useDiff(materialId: string, before: string | null, after: string) {
  return useQuery({
    queryKey: [...baselinesKey(materialId), 'diff', before, after],
    queryFn: () => fetchDiff(materialId, before ?? '', after),
    enabled: Boolean(before),
  });
}

function useServerMutation<TVars, TResult>(materialId: string, mutationFn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      for (const key of touched(materialId)) void queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (error) => notifyError(error, t),
  });
}

export function useCreateBaseline(materialId: string) {
  return useServerMutation(materialId, () => createBaseline(materialId));
}

export function useRequestAuthorization(materialId: string) {
  return useServerMutation(materialId, (body: { kind: string; description: string; reason: string }) => requestAuthorization(materialId, body));
}

type BaselineStep = { baseline: Baseline; action: 'withdraw' | 'approve' | 'reject'; comment?: string | null };
const NEXT_BASELINE: Record<BaselineStep['action'], Baseline['state']> = { withdraw: 'retirada', approve: 'revisada', reject: 'rechazada' };

export function useBaselineStep(materialId: string) {
  return useOptimisticMutation<Baseline, BaselineStep, Baseline>({
    queryKey: [...listKey(materialId)],
    mutationFn: ({ baseline, action, comment }) =>
      action === 'withdraw' ? withdrawBaseline(materialId, baseline) : reviewBaseline(materialId, baseline, action === 'approve', comment ?? null),
    apply: (list, { baseline, action, comment }) =>
      list.map((b) => (b.id === baseline.id ? { ...b, state: NEXT_BASELINE[action], review_comment: comment ?? b.review_comment } : b)),
    settle: (list, saved) => list.map((b) => (b.id === saved.id ? saved : b)),
    invalidate: touched(materialId),
  });
}

type AuthorizationStep = { authorization: ChangeAuthorization; action: 'approve' | 'reject' | 'close'; comment?: string | null };
const NEXT_AUTHORIZATION: Record<AuthorizationStep['action'], ChangeAuthorization['state']> = { approve: 'aprobada', reject: 'rechazada', close: 'cerrada' };

export function useAuthorizationStep(materialId: string) {
  return useOptimisticMutation<ChangeAuthorization, AuthorizationStep, ChangeAuthorization>({
    queryKey: [...authorizationsKey(materialId)],
    mutationFn: ({ authorization, action, comment }) =>
      action === 'close'
        ? closeAuthorization(materialId, authorization)
        : decideAuthorization(materialId, authorization, action === 'approve', comment ?? null),
    apply: (list, { authorization, action }) => list.map((a) => (a.id === authorization.id ? { ...a, state: NEXT_AUTHORIZATION[action] } : a)),
    settle: (list, saved) => list.map((a) => (a.id === saved.id ? saved : a)),
    invalidate: touched(materialId),
  });
}

/** The authorization chosen for this CUF's edits, while it is still usable (approved, open). */
export function useActiveAuthorization(materialId: string): ChangeAuthorization | null {
  const chosen = useUiStore((s) => s.changeAuthorizations[materialId]);
  const state = useConfigurationState(materialId);
  return state.data?.usable_authorizations.find((a) => a.id === chosen) ?? null;
}

/** Whether the CONFUNFIS may be edited now: hidden without the permission, otherwise disabled
 *  while a baseline is in review or a reviewed one has no active authorization (E17b), with the
 *  reason and the link that unblocks it. The server refuses it anyway. */
export function useEditGate(materialId: string, permitted: boolean, canRequest = false): Gate & { canEdit: boolean } {
  const { t } = useTranslation();
  const state = useConfigurationState(materialId, permitted);
  const active = useActiveAuthorization(materialId);
  const page = `/materiales/${materialId}/baselines`;
  const s = state.data;
  let gate: Gate = { permitted, reason: null, unlock: null };
  if (permitted && s?.edit === 'locked') {
    gate = { permitted, reason: t('baselines.band.lockedReason', { number: s.in_review?.number }), unlock: { to: page, label: t('baselines.band.open') } };
  } else if (permitted && s?.edit === 'authorization' && !active) {
    gate = {
      permitted,
      reason: s.usable_authorizations.length ? t('baselines.band.chooseAuthorization') : t('baselines.band.needAuthorization'),
      unlock: canRequest ? { to: `${page}?tab=autorizaciones`, label: t('baselines.band.request') } : { to: page, label: t('baselines.band.open') },
    };
  }
  return { ...gate, canEdit: permitted && !gate.reason };
}
