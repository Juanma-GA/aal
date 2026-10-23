import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { describeApiError } from '@/services/apiErrors';
import { fetchSns } from '@/services/catalogApi';

const ORIGIN_KEYS = { ELEMENTO: 'elemento', 'CN-001': 'cn001', OTRA_SUBCATEGORIA: 'otherSubcategory' } as const;

function Link({ sns, name, onOpen }: { sns: string; name: string; onOpen: (sns: string) => void }): React.JSX.Element {
  return (
    <button type="button" className="text-left text-link underline-offset-2 hover:underline" onClick={() => onOpen(sns)} data-testid={`sns-link-${sns}`}>
      <span className="font-mono text-xs">{sns}</span> {name}
    </button>
  );
}

/** An SNS of a version: names, description, level, parent, children and
 *  where it appears. */
export function SnsCard({ versionId, sns, onOpen, onSubcategory }: {
  versionId: string;
  sns: string | null;
  onOpen: (sns: string) => void;
  onSubcategory: (code: string, sns: string) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  const detail = useQuery({ queryKey: ['catalog', versionId, 'sns', sns], queryFn: () => fetchSns(versionId, sns ?? ''), enabled: Boolean(sns) });
  if (!sns) return <p className="text-sm text-muted-foreground">{t('catalog.chooseSns')}</p>;
  if (detail.isError) return <p className="text-sm text-destructive" role="alert">{describeApiError(detail.error, t).message}</p>;
  if (!detail.data) return <Skeleton className="h-60 w-full" />;
  const d = detail.data;
  return (
    <Card data-testid="sns-card">
      <CardHeader>
        <CardTitle>
          <span className="font-mono">{d.sns}</span> · {d.name}
        </CardTitle>
        <CardDescription>
          {t(`catalog.levels.${d.level}`)}
          {d.declared_levels.length ? ` · ${t('catalog.declared')}: ${d.declared_levels.map((l) => t(`catalog.levels.${l}`)).join(', ')}` : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        <section>
          <h4 className="font-medium">{t('catalog.description')}</h4>
          <p className="whitespace-pre-wrap text-muted-foreground">{d.description}</p>
          {d.description_pending ? (
            <Badge variant="outline" className="mt-1 border-warning text-warning">
              {t('catalog.pending')}
            </Badge>
          ) : null}
        </section>
        {d.extra_names.length ? (
          <section data-testid="sns-extra-names">
            <h4 className="font-medium">{t('catalog.extraNames')}</h4>
            <ul className="flex flex-col gap-1">
              {d.extra_names.map((e) => (
                <li key={e.name} className="flex flex-wrap items-center gap-2">
                  {e.name}
                  <Badge variant="secondary">{t(`catalog.origins.${ORIGIN_KEYS[e.origin]}`)}</Badge>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <section>
          <h4 className="font-medium">{t('catalog.parent')}</h4>
          {d.parent ? (
            <Link sns={d.parent.sns} name={d.parent.name} onOpen={onOpen} />
          ) : d.parent_sns ? (
            <p className="text-warning">{t('catalog.parentMissing', { sns: d.parent_sns })}</p>
          ) : (
            <p className="text-muted-foreground">{t('catalog.noParent')}</p>
          )}
        </section>
        {d.children.length ? (
          <section>
            <h4 className="font-medium">{t('catalog.children', { count: d.children.length })}</h4>
            <ul className="flex flex-col gap-1">
              {d.children.map((c) => (
                <li key={c.sns}>
                  <Link sns={c.sns} name={c.name} onOpen={onOpen} />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <section data-testid="sns-appearances">
          <h4 className="font-medium">{t('catalog.appearances')}</h4>
          <ul className="flex flex-col gap-1">
            {d.appearances.map((a) => (
              <li key={a.row_number}>
                {a.subcategory_code ? (
                  <button type="button" className="text-left text-link underline-offset-2 hover:underline" onClick={() => onSubcategory(a.subcategory_code ?? '', d.sns)}>
                    <span className="font-mono text-xs">{a.subcategory_code}</span> {a.subcategory_name}
                  </button>
                ) : (
                  <span className="text-warning">{t('catalog.noSubcategory')}</span>
                )}
                <span className="text-muted-foreground">
                  {' '}
                  · {t('catalog.row', { row: a.row_number })} · {t(`catalog.levels.${a.declared_level}`)}
                  {a.name !== d.name ? ` · ${a.name}` : ''}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </CardContent>
    </Card>
  );
}
