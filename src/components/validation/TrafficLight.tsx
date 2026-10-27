import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { LightState, Validation } from '@/types/validation';

const LIGHT: Record<LightState, string> = {
  red: 'bg-destructive',
  amber: 'bg-warning',
  green: 'bg-success',
  none: 'bg-muted-foreground',
};

/** The traffic light of a CUF's latest validation (E16): red with blocking
 *  findings, amber with warnings, green without blocking ones; and
 *  "desactualizado" when the CUF or the rules changed since. */
export function TrafficLight({ validation, compact = false }: { validation: Validation; compact?: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const { state } = validation;
  return (
    <div className={cn('flex flex-wrap items-center gap-3', compact && 'gap-2')} data-testid="validation-light" data-state={state}>
      <span aria-hidden="true" className={cn('inline-block shrink-0 rounded-full', LIGHT[state], compact ? 'size-3' : 'size-6')} />
      <span className={cn('font-medium', compact ? 'text-sm' : 'text-lg')} data-testid="validation-state">{t(`validation.state.${state}`)}</span>
      {state !== 'none' ? (
        <span className="flex flex-wrap items-center gap-1">
          <Badge variant={validation.blocking ? 'destructive' : 'secondary'} data-testid="validation-blocking">{t('validation.page.blocking', { count: validation.blocking })}</Badge>
          <Badge variant={validation.warnings ? 'warning' : 'secondary'} data-testid="validation-warnings">{t('validation.page.warnings', { count: validation.warnings })}</Badge>
          {validation.accepted ? <Badge variant="outline" data-testid="validation-accepted">{t('validation.page.accepted', { count: validation.accepted })}</Badge> : null}
        </span>
      ) : null}
      {validation.outdated ? <Badge variant="warning" data-testid="validation-outdated">{t('validation.page.outdated')}</Badge> : null}
    </div>
  );
}
