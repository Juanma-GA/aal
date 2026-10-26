import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';

/** A row's observations (E13, provisional codes OF-*), as badges: their
 *  short names, or just how many in `compact` (the tree). */
export function ObservationBadges({ row, compact = false }: { row: { sns?: string; observation_codes: readonly string[] }; compact?: boolean }): React.JSX.Element | null {
  const { t } = useTranslation();
  if (!row.observation_codes.length) return null;
  const title = row.observation_codes.map((c) => t(`confunfis.observations.${c}.short`)).join(' · ');
  if (compact) {
    return (
      <Badge variant="outline" className="shrink-0 border-warning text-warning" title={title} data-testid={`row-observations-${row.sns}`}>
        {t('confunfis.observationsCount', { count: row.observation_codes.length })}
      </Badge>
    );
  }
  return (
    <span className="flex flex-wrap gap-1">
      {row.observation_codes.map((code) => (
        <Badge key={code} variant="outline" className="border-warning text-warning" data-testid={`row-observation-${code}`}>
          {t(`confunfis.observations.${code}.short`)}
        </Badge>
      ))}
    </span>
  );
}
