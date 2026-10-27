import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useUpdateValidationRule, useValidationRules } from '@/hooks/useValidation';
import type { Severity, ValidationRule } from '@/types/validation';

const SEVERITIES: Exclude<Severity, 'desactivada'>[] = ['bloqueante', 'aviso'];

/** A text saved when it loses the focus (or Enter), only if it changed. */
function BlurInput({ value, onSave, label, testId }: { value: string; onSave: (v: string) => void; label: string; testId: string }): React.JSX.Element {
  const [text, setText] = useState(value);
  const save = () => { if (text !== value) onSave(text); };
  return (
    <Input
      value={text} aria-label={label} className="h-8" data-testid={testId}
      onChange={(e) => setText(e.target.value)} onBlur={save} onKeyDown={(e) => { if (e.key === 'Enter') save(); }}
    />
  );
}

/** The NT 10/17 rules (E16): active, severity, parameters and the admin's
 *  help text. Every change is audited and leaves the CUF's validations
 *  "desactualizado" until they are run again. Shown at once, undone if
 *  the server refuses it (HR20). */
export function ValidationRulesTab(): React.JSX.Element {
  const { t } = useTranslation();
  const rules = useValidationRules();
  const update = useUpdateValidationRule();
  if (!rules.data) return <Skeleton className="h-60 w-full" />;
  const change = (rule: ValidationRule, patch: Parameters<typeof update.mutate>[0]['patch']) => update.mutate({ rule, patch });
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('settings.validationRules.hint')}</p>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('validation.page.code')}</TableHead>
              <TableHead>{t('validation.page.ruleText')}</TableHead>
              <TableHead>{t('validation.report.ref')}</TableHead>
              <TableHead>{t('settings.validationRules.active')}</TableHead>
              <TableHead>{t('validation.report.severity')}</TableHead>
              <TableHead>{t('settings.validationRules.params')}</TableHead>
              <TableHead>{t('settings.validationRules.help')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.data.map((rule) => (
              <TableRow key={rule.code} data-testid={`rule-${rule.code}`}>
                <TableCell className="font-mono align-top">{rule.code}</TableCell>
                <TableCell className="min-w-64 whitespace-normal align-top">
                  <p className="font-medium">{t(`validation.rules.${rule.code}.title`)}</p>
                  <p className="text-xs text-muted-foreground">{t(`validation.rules.${rule.code}.text`)}</p>
                  <Badge variant="outline" className="mt-1">{t(`validation.scope.${rule.scope}`)}</Badge>
                </TableCell>
                <TableCell className="align-top text-muted-foreground">{rule.ref}</TableCell>
                <TableCell className="align-top">
                  <Switch
                    checked={rule.active} aria-label={t('settings.validationRules.activeOf', { code: rule.code })}
                    onCheckedChange={(active) => change(rule, { active })} data-testid={`rule-active-${rule.code}`}
                  />
                </TableCell>
                <TableCell className="align-top">
                  <Select value={rule.severity} onValueChange={(v) => change(rule, { severity: v as Severity })} disabled={!rule.active}>
                    <SelectTrigger className="w-36" aria-label={t('settings.validationRules.severityOf', { code: rule.code })} data-testid={`rule-severity-${rule.code}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SEVERITIES.map((s) => (
                        <SelectItem key={s} value={s}>{t(`validation.severity.${s}`)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {rule.active ? t('settings.validationRules.defaultIs', { severity: t(`validation.severity.${rule.default_severity}`) }) : t('validation.severity.desactivada')}
                  </p>
                </TableCell>
                <TableCell className="align-top">
                  {Object.keys(rule.params).length ? (
                    <span className="flex flex-col gap-1">
                      {Object.entries(rule.params).map(([key, value]) => (
                        <label key={key} className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground">{t(`settings.validationRules.paramNames.${key}`)}</span>
                          <BlurInput
                            value={String(value ?? '')} label={t(`settings.validationRules.paramNames.${key}`)} testId={`rule-param-${rule.code}-${key}`}
                            onSave={(v) => change(rule, { params: { ...rule.params, [key]: v } })}
                          />
                        </label>
                      ))}
                    </span>
                  ) : <span className="text-xs text-muted-foreground">{t('settings.validationRules.noParams')}</span>}
                </TableCell>
                <TableCell className="min-w-44 align-top">
                  <BlurInput
                    value={rule.help ?? ''} label={t('settings.validationRules.helpOf', { code: rule.code })} testId={`rule-help-${rule.code}`}
                    onSave={(v) => change(rule, { help: v.trim() || null })}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
