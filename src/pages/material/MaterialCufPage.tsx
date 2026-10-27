// Materiales / CUF (E11): the material's card. Its data and family, its
// catalog version, its team and its subcategories; the normalized
// configuration the CONFUNFIS will start from; and the requests for a new
// SNS. The tab lives in the URL (?tab), nothing in the browser (HR1).
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { CatalogVersionCard } from '@/components/cuf/CatalogVersionCard';
import { CufDataCard } from '@/components/cuf/CufDataCard';
import { NormalizedConfigTab } from '@/components/cuf/NormalizedConfigTab';
import { SnsRequestsTab } from '@/components/cuf/SnsRequestsTab';
import { SubcategoriesCard } from '@/components/cuf/SubcategoriesCard';
import { ConfigurationBand } from '@/components/baselines/ConfigurationBand';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useEditGate } from '@/hooks/useBaselines';
import { useCuf } from '@/hooks/useCuf';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { useMe } from '@/hooks/useSession';
import { catalogLabel } from '@/lib/labels';
import { describeApiError } from '@/services/apiErrors';
import { fetchTeam } from '@/services/modulesApi';

const TABS = ['ficha', 'configuracion', 'solicitudes'] as const;
type Tab = (typeof TABS)[number];

function TeamCard({ materialId }: { materialId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const team = useQuery({ queryKey: ['materials', materialId, 'team'], queryFn: () => fetchTeam(materialId) });
  return (
    <Card data-testid="cuf-team">
      <CardHeader>
        <CardTitle>{t('panel.team')}</CardTitle>
      </CardHeader>
      <CardContent>
        {!team.data ? (
          <Skeleton className="h-16 w-full" />
        ) : team.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('panel.noTeam')}</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {team.data.map((m) => (
              <li key={`${m.display_name}-${m.role}`} className="flex justify-between gap-2">
                <span>{m.display_name}</span>
                <span className="text-muted-foreground">{catalogLabel(t, 'roles', m.role)}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function MaterialCufPage(): React.JSX.Element {
  const { t } = useTranslation();
  const material = useMaterialOfPage();
  const me = useMe();
  const cuf = useCuf(material.id);
  const [params, setParams] = useSearchParams();
  const tab: Tab = TABS.find((x) => x === params.get('tab')) ?? 'ficha';
  const isAdmin = Boolean(me.data?.is_admin);
  const canEdit = material.permissions.includes('material.editar');
  // E17b: subcategories and catalog version are change-controlled after a baseline (the band chooses the authorization).
  const canRequest = material.permissions.includes('autorizacion.solicitar');
  const subcategoriesGate = useEditGate(material.id, canEdit, canRequest);
  const versionGate = useEditGate(material.id, isAdmin, canRequest);
  const title = t('cuf.title');
  return (
    <div className="flex flex-col gap-6" data-testid="cuf-page">
      <PageHeader crumbs={[{ label: material.name, to: `/materiales/${material.id}` }, { label: title }]} title={title} />
      <ConfigurationBand materialId={material.id} canRequest={canRequest} />
      {cuf.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {describeApiError(cuf.error, t).message}
        </p>
      ) : !cuf.data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <Tabs value={tab} onValueChange={(v) => setParams(v === 'ficha' ? {} : { tab: v })}>
          <TabsList>
            {TABS.map((name) => (
              <TabsTrigger key={name} value={name} data-testid={`cuf-tab-${name}`}>
                {t(`cuf.tabs.${name}`)}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="ficha" className="grid gap-6 lg:grid-cols-2">
            <CufDataCard material={material} cuf={cuf.data} isAdmin={isAdmin} />
            <SubcategoriesCard cuf={cuf.data} gate={subcategoriesGate} />
            <CatalogVersionCard cuf={cuf.data} gate={versionGate} />
            <TeamCard materialId={material.id} />
          </TabsContent>
          <TabsContent value="configuracion">
            <NormalizedConfigTab cuf={cuf.data} />
          </TabsContent>
          <TabsContent value="solicitudes">
            <SnsRequestsTab materialId={material.id} canEdit={canEdit} isAdmin={isAdmin} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
