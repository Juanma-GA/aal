import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { humanize } from '@/lib/humanize';
import { fetchParameters } from '@/services/adminApi';

/** Every leaf of a nested value, as ["a.b", value]. */
function leaves(value: Record<string, unknown>, prefix = ''): [string, unknown][] {
  return Object.entries(value).flatMap(([key, v]) =>
    v !== null && typeof v === 'object' && !Array.isArray(v) ? leaves(v as Record<string, unknown>, `${prefix}${key}.`) : [[`${prefix}${key}`, v]],
  );
}

/** The parameters in force, read-only in this version. */
export function ParametersTab(): React.JSX.Element {
  const { t } = useTranslation();
  const parameters = useQuery({ queryKey: ['parameters'], queryFn: fetchParameters });
  if (!parameters.data) return <Skeleton className="h-60 w-full" />;
  const groups = t('settings.parameters.groups', { returnObjects: true }) as Record<string, string>;
  const labels = t('settings.parameters.labels', { returnObjects: true }) as Record<string, string>;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('settings.parameters.hint')}</p>
      {parameters.data.map((p) => (
        <Card key={p.key} data-testid={`parameters-${p.key}`}>
          <CardHeader>
            <CardTitle>{groups[p.key] ?? humanize(p.key)}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl>
              {leaves(p.value).map(([path, value]) => (
                <div key={path} className="flex flex-col gap-1 border-t py-2 first:border-t-0 sm:flex-row sm:justify-between">
                  <dt className="text-sm text-muted-foreground">{labels[path] ?? humanize(path)}</dt>
                  <dd className="font-mono text-sm text-foreground">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
