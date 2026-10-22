import { Info } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { ModuleStatusBadge, ModuleStatusIcon } from '@/components/modules/ModuleStatus';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { moduleCardHref, moduleHref, useModule } from '@/hooks/useModules';
import { ApiError } from '@/services/apiClient';
import type { ModuleLink } from '@/types/modules';
import { NotFoundPage } from './NotFoundPage';

function List({ items, empty }: { items: string[]; empty: string }): React.JSX.Element {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="list-inside list-disc text-sm text-foreground">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function Links({ links, materialId, empty, testId }: { links: ModuleLink[]; materialId: string; empty: string; testId: string }): React.JSX.Element {
  if (links.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="flex flex-col gap-2" data-testid={testId}>
      {links.map((l) => (
        <li key={l.code} className="flex items-center gap-2">
          <ModuleStatusIcon status={l.status} />
          <Link className="text-sm text-brand underline-offset-4 hover:underline" to={moduleCardHref(l.code, materialId)}>
            {l.name}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A module's card (D7): what it is for and how far it is. A planned
 *  module says so plainly and offers nothing it cannot do. */
export function ModulePage(): React.JSX.Element {
  const { t } = useTranslation();
  const { code } = useParams();
  const material = useMaterialOfPage();
  const module = useModule(code);
  if (module.error instanceof ApiError && module.error.status === 404) return <NotFoundPage kind="module" />;
  if (!module.data) return <Skeleton className="h-60 w-full" />;
  const m = module.data;
  return (
    <div className="flex flex-col gap-6" data-testid="module-card">
      <PageHeader
        crumbs={[{ label: material.name, to: `/materiales/${material.id}` }, { label: m.group_name }, { label: m.name }]}
        title={m.name}
      >
        <ModuleStatusBadge status={m.status} />
        <Badge variant="secondary">{t(`modules.phase.${m.phase}`)}</Badge>
      </PageHeader>
      {m.status === 'planificado' ? (
        <Alert data-testid="module-planned">
          <Info aria-hidden="true" />
          <AlertTitle>{t('modules.plannedTitle')}</AlertTitle>
          <AlertDescription>{t('modules.planned')}</AlertDescription>
        </Alert>
      ) : m.status === 'en_desarrollo' ? (
        <Alert data-testid="module-in-progress">
          <Info aria-hidden="true" />
          <AlertTitle>{t('modules.inProgressTitle')}</AlertTitle>
          <AlertDescription>{t('modules.inProgress')}</AlertDescription>
        </Alert>
      ) : m.route ? (
        <div>
          <Button asChild>
            <Link to={moduleHref(m, material.id)}>{t('modules.open')}</Link>
          </Button>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t('modules.objective')}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-foreground">{m.objective || t('modules.none')}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('modules.requirements')}</CardTitle>
        </CardHeader>
        <CardContent>
          {m.requirements.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('modules.noRequirements')}</p>
          ) : (
            <ul className="flex flex-col gap-3" data-testid="module-requirements">
              {m.requirements.map((r) => (
                <li key={r.rf_id} className="flex flex-col gap-1 sm:flex-row sm:gap-3">
                  <Badge variant="outline" className="h-fit font-mono">
                    {r.rf_id}
                  </Badge>
                  <span className="text-sm text-foreground">{r.text}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{t('modules.inputs')}</CardTitle>
          </CardHeader>
          <CardContent>
            <List items={m.inputs} empty={t('modules.none')} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('modules.outputs')}</CardTitle>
          </CardHeader>
          <CardContent>
            <List items={m.outputs} empty={t('modules.none')} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('modules.deliverable')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-foreground">{m.deliverable ?? t('modules.noDeliverable')}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('modules.dependsOn')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Links links={m.depends_on} materialId={material.id} empty={t('modules.noDependencies')} testId="module-depends-on" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('modules.usedBy')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Links links={m.used_by} materialId={material.id} empty={t('modules.noUsers')} testId="module-used-by" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
