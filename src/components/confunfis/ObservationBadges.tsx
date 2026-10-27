import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { findingTitle } from '@/lib/confunfisText';

/** A row's findings (E16: the NT rules' codes), as badges: code and short
 *  name, or just how many in `compact` (the tree). */
export function ObservationBadges({ row, compact = false }: { row: { sns?: string; observation_codes: readonly string[] }; compact?: boolean }): React.JSX.Element | null {
  const { t } = useTranslation();
  if (!row.observation_codes.length) return null;
  const title = row.observation_codes.map((c) => `${c} ${findingTitle(t, c)}`).join(' · ');
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
        <Badge key={code} variant="outline" className="border-warning text-warning" title={findingTitle(t, code)} data-testid={`row-observation-${code}`}>
          {code}
        </Badge>
      ))}
    </span>
  );
}
