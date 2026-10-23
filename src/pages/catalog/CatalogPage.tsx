// Configuración funcional normalizada (E10, RF-01): the SNS catalog of the
// Army, common to the whole app (it hangs from no material), with its
// versions. Three panels: categories -> subcategories, the subcategory's
// tree, the SNS card. What is chosen lives in the URL (?v, sub, sns, tab),
// so a link opens the same view and nothing is kept in the browser (HR1).
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { CatalogSearch } from '@/components/catalog/CatalogSearch';
import { CategoryPanel } from '@/components/catalog/CategoryPanel';
import { CompareView } from '@/components/catalog/CompareView';
import { SnsCard } from '@/components/catalog/SnsCard';
import { SnsTree } from '@/components/catalog/SnsTree';
import { WarningsView } from '@/components/catalog/WarningsView';
import { ImportWizard } from '@/components/import/ImportWizard';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useMe } from '@/hooks/useSession';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { exportCatalog, fetchCatalogVersions, fetchCategories, startCatalogImport } from '@/services/catalogApi';

export const CATALOG_PATH = '/configuracion-funcional';
const TABS = ['catalogo', 'avisos', 'comparar'] as const;
type Tab = (typeof TABS)[number];

export function CatalogPage(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [importing, setImporting] = useState(false);
  const versions = useQuery({ queryKey: ['catalog', 'versions'], queryFn: fetchCatalogVersions });
  const list = versions.data ?? [];
  const version = list.find((v) => v.id === params.get('v')) ?? list.find((v) => v.is_active) ?? list[0];
  const categories = useQuery({ queryKey: ['catalog', version?.id, 'categories'], queryFn: () => fetchCategories(version?.id ?? ''), enabled: Boolean(version) });
  const sub = params.get('sub');
  const sns = params.get('sns');
  const tab: Tab = TABS.find((x) => x === params.get('tab')) ?? 'catalogo';
  const isAdmin = Boolean(me.data?.is_admin);

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    setParams(next);
  };
  const openSns = (code: string) => update({ sns: code, tab: null });
  const doExport = (subcategory?: string) => {
    if (!version) return;
    exportCatalog(version.id, subcategory)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? 'CONF_FUN.xlsx'))
      .catch((error: unknown) => notifyError(error, t));
  };
  const imported = () => {
    void queryClient.invalidateQueries({ queryKey: ['catalog'] });
    update({ v: null, sub: null, sns: null });
  };

  const header = <PageHeader crumbs={[{ label: t('catalog.title') }]} title={t('catalog.title')} />;
  if (!versions.data) return <div className="flex flex-col gap-6">{header}<Skeleton className="h-96 w-full" /></div>;

  return (
    <div className="flex flex-col gap-6" data-testid="catalog-page">
      {header}
      <p className="text-sm text-muted-foreground">{t('catalog.hint')}</p>
      <div className="flex flex-wrap items-start gap-2">
        {version ? (
          <>
            <Select value={version.id} onValueChange={(v) => update({ v, sub: null, sns: null })}>
              <SelectTrigger className="w-full sm:w-80" aria-label={t('catalog.version')} data-testid="catalog-version">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {list.map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    {t('catalog.versionLabel', { number: v.number, label: v.label })}
                    {v.is_active ? ` · ${t('catalog.active')}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <CatalogSearch
              key={version.id}
              versionId={version.id}
              onPick={(hit) => update({ sns: hit.sns, tab: null, sub: sub && hit.subcategories.includes(sub) ? sub : (hit.subcategories[0] ?? sub) })}
            />
          </>
        ) : null}
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          {version ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" data-testid="catalog-export">
                  {t('reference.export')}
                  <ChevronDown aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => doExport()} data-testid="catalog-export-all">
                  {t('catalog.exportVersion')}
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!sub} onSelect={() => sub && doExport(sub)} data-testid="catalog-export-sub">
                  {sub ? t('catalog.exportSubcategory', { code: sub }) : t('catalog.exportChooseSubcategory')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          {isAdmin ? (
            <Button onClick={() => setImporting(true)} data-testid="catalog-import">
              {t('catalog.import')}
            </Button>
          ) : null}
        </div>
      </div>

      {!version ? (
        <p className="text-sm text-muted-foreground" data-testid="catalog-empty">
          {isAdmin ? t('catalog.emptyAdmin') : t('catalog.empty')}
        </p>
      ) : (
        <Tabs value={tab} onValueChange={(v) => update({ tab: v === 'catalogo' ? null : v })}>
          <TabsList>
            {TABS.map((name) => (
              <TabsTrigger key={name} value={name} data-testid={`catalog-tab-${name}`}>
                {t(`catalog.tabs.${name}`)}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="catalogo">
            <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)_24rem]">
              <CategoryPanel categories={categories.data} selected={sub} onSelect={(code) => update({ sub: code })} />
              <div className="min-w-0">
                {sub ? (
                  <SnsTree key={`${version.id}-${sub}`} versionId={version.id} subcategory={sub} selected={sns} onSelect={openSns} />
                ) : (
                  <p className="text-sm text-muted-foreground">{t('catalog.chooseSubcategory')}</p>
                )}
              </div>
              <SnsCard versionId={version.id} sns={sns} onOpen={openSns} onSubcategory={(code, s) => update({ sub: code, sns: s })} />
            </div>
          </TabsContent>
          <TabsContent value="avisos">
            <WarningsView versionId={version.id} onOpen={openSns} />
          </TabsContent>
          <TabsContent value="comparar">
            <CompareView versions={list} onOpen={(s) => update({ sns: s, tab: null })} />
          </TabsContent>
        </Tabs>
      )}

      {isAdmin ? (
        <ImportWizard open={importing} onOpenChange={setImporting} title={t('catalog.importTitle')} start={startCatalogImport} onApplied={imported} />
      ) : null}
    </div>
  );
}
