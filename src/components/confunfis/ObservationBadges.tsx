import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useValidationRules } from '@/hooks/useValidation';
import { findingTitle } from '@/lib/confunfisText';

/** A row's findings (E16: the NT rules' codes), as badges -- pressing one
 *  tells the rule in words and its section of the NT --, or just how many
 *  in `compact` (the tree). */
export function ObservationBadges({ row, compact = false }: { row: { sns?: string; observation_codes: readonly string[] }; compact?: boolean }): React.JSX.Element | null {
  const { t } = useTranslation();
  const rules = useValidationRules();
  if (!row.observation_codes.length) return null;
  const title = row.observation_codes.map((c) => `${c} ${findingTitle(t, c)}`).join(' · ');
  if (compact) {
    return (
      <Badge variant="warning" className="shrink-0" title={title} data-testid={`row-observations-${row.sns}`}>
        {t('confunfis.observationsCount', { count: row.observation_codes.length })}
      </Badge>
    );
  }
  const severity = (code: string) => rules.data?.find((r) => r.code === code);
  return (
    <span className="flex flex-wrap gap-1">
      {row.observation_codes.map((code) => {
        const rule = severity(code);
        const blocking = rule?.active !== false && rule?.severity === 'bloqueante';
        return (
          <Popover key={code}>
            <PopoverTrigger asChild>
              <button type="button" className="rounded-full focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none" onClick={(e) => e.stopPropagation()} aria-label={`${code} ${findingTitle(t, code)}`}>
                <Badge variant={blocking ? 'destructive' : 'warning'} data-testid={`row-observation-${code}`}>{code}</Badge>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-80 text-sm" onClick={(e) => e.stopPropagation()} data-testid={`rule-popover-${code}`}>
              <p className="font-medium">{code} · {findingTitle(t, code)}</p>
              <p className="text-muted-foreground">{t(`validation.rules.${code}.text`)}</p>
              {rule ? <p className="mt-1 text-xs">{t('validation.page.refAndSeverity', { ref: rule.ref, severity: t(`validation.severity.${rule.active ? rule.severity : 'desactivada'}`) })}</p> : null}
            </PopoverContent>
          </Popover>
        );
      })}
    </span>
  );
}
