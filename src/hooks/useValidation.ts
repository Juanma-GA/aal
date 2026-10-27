import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { useArticleFields } from '@/hooks/useReferenceTables';
import { findingText } from '@/lib/articleText';
import { notifyError } from '@/lib/notify';
import { acceptFinding, fetchValidation, fetchValidationRules, runValidation, updateValidationRule } from '@/services/validationApi';
import type { Finding, Severity, Validation, ValidationRule } from '@/types/validation';

export const validationKey = (materialId: string) => ['validation', materialId] as const;
export const validationRulesKey = ['validation-rules'] as const;

/** The latest validation of a CUF. "Desactualizado" is the server's: read
 *  again whenever the CONFUNFIS changes (its key) or the page comes back. */
export function useValidation(materialId: string) {
  return useQuery({ queryKey: validationKey(materialId), queryFn: () => fetchValidation(materialId), refetchOnWindowFocus: true });
}

/** "Validar ahora": a full run on the server; its id and counts are the
 *  server's, so it is not optimistic (as creating a material, HR20). */
export function useRunValidation(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: () => runValidation(materialId),
    onSuccess: (data) => {
      queryClient.setQueryData(validationKey(materialId), data);
      void queryClient.invalidateQueries({ queryKey: ['confunfis', materialId] });
    },
    onError: (error) => notifyError(error, t),
  });
}

/** Accepting a warning: shown at once, undone if the server refuses (HR20). */
export function useAcceptFinding(materialId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const key = validationKey(materialId);
  return useMutation({
    mutationFn: ({ id, justification }: { id: string; justification: string }) => acceptFinding(materialId, id, justification),
    onMutate: async ({ id, justification }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Validation>(key);
      if (previous) {
        queryClient.setQueryData<Validation>(key, {
          ...previous,
          warnings: Math.max(0, previous.warnings - 1),
          accepted: previous.accepted + 1,
          findings: previous.findings.map((f) => (f.id === id ? { ...f, accepted: true, justification } : f)),
        });
      }
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
      notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: key }));
    },
    onSuccess: (data) => queryClient.setQueryData(key, data),
  });
}

export function useValidationRules() {
  return useQuery({ queryKey: validationRulesKey, queryFn: fetchValidationRules });
}

type RulePatch = { active?: boolean; severity?: Severity; params?: Record<string, unknown>; help?: string | null };

/** The admin's change of a rule (HR20): every validation becomes "desactualizado". */
export function useUpdateValidationRule() {
  return useOptimisticMutation<ValidationRule, { rule: ValidationRule; patch: RulePatch }, ValidationRule>({
    queryKey: [...validationRulesKey],
    mutationFn: ({ rule, patch }) => updateValidationRule(rule.code, rule.version, patch),
    apply: (list, { rule, patch }) => list.map((r) => (r.code === rule.code ? { ...r, ...patch } : r)),
    settle: (list, saved) => list.map((r) => (r.code === saved.code ? saved : r)),
    invalidate: [['validation']],
  });
}

/** A finding in words (an AR one with the fields by their names, HR21). */
export function useFindingMessage(): (f: Finding) => string {
  const { t } = useTranslation();
  const fields = useArticleFields();
  const names = useMemo(() => Object.fromEntries((fields.data ?? []).map((f) => [f.prisma_code, f.name])), [fields.data]);
  return (f) =>
    f.rule_code.startsWith('AR-')
      ? findingText(t, { problem: f.problem, field: f.field ?? '', params: f.params }, names)
      : t(`validation.problems.${f.rule_code}.${f.problem}`, { ...f.params, defaultValue: t(`validation.rules.${f.rule_code}.title`) });
}
