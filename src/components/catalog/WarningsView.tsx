import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { fetchCatalogWarnings } from '@/services/catalogApi';

const CODES = ['cn_001', 'cn_002', 'cn_003', 'cn_004', 'cn_005', 'cn_006'] as const;

/** "Avisos de la versión": the incoherences of the catalog itself
 *  (CN-001..CN-006) found when it was imported, each with its SNS. */
export function WarningsView({ versionId, onOpen }: { versionId: string; onOpen: (sns: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const warnings = useQuery({ queryKey: ['catalog', versionId, 'warnings'], queryFn: () => fetchCatalogWarnings(versionId) });
  if (!warnings.data) return <Skeleton className="h-60 w-full" />;
  return (
    <div className="flex flex-col gap-4" data-testid="catalog-warnings">
      <p className="text-sm text-muted-foreground">{t('catalog.warningsHint')}</p>
      {CODES.map((code) => {
        const items = warnings.data.items.filter((w) => w.code === code);
        return (
          <Card key={code} data-testid={`warnings-${code}`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {t(`catalog.warnings.${code}.title`)}
                <Badge variant={items.length ? 'secondary' : 'outline'} data-testid={`warnings-count-${code}`}>
                  {warnings.data.counts[code] ?? 0}
                </Badge>
              </CardTitle>
              <CardDescription>{t(`catalog.warnings.${code}.hint`)}</CardDescription>
            </CardHeader>
            {items.length ? (
              <CardContent>
                <ul className="flex flex-col gap-1 text-sm">
                  {items.map((w, i) => (
                    <li key={`${w.row ?? 0}-${i}`} className="flex flex-wrap gap-2">
                      <button type="button" className="font-mono text-link underline-offset-2 hover:underline" onClick={() => onOpen(String(w.params.sns))}>
                        {String(w.params.sns)}
                      </button>
                      <span className="text-muted-foreground">{t('catalog.row', { row: w.row ?? 0 })}</span>
                      <span>{t(`import.issues.${code}`, w.params)}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            ) : null}
          </Card>
        );
      })}
    </div>
  );
}
