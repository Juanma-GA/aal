import { useTranslation } from 'react-i18next';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const SETTINGS_TABS = [
  { path: 'usuarios', label: 'settings.tabs.users' },
  { path: 'materiales', label: 'settings.tabs.materials' },
  { path: 'roles', label: 'settings.tabs.roles' },
  { path: 'auditoria', label: 'settings.tabs.audit' },
  { path: 'modulos', label: 'settings.tabs.modules' },
  { path: 'tablas-referencia', label: 'settings.tabs.referenceTables' },
  { path: 'campos-articulo', label: 'settings.tabs.articleFields' },
  { path: 'parametros', label: 'settings.tabs.parameters' },
] as const;

export function SettingsLayout(): React.JSX.Element {
  const { t } = useTranslation();
  const location = useLocation();
  const tab = SETTINGS_TABS.find((tab) => location.pathname.startsWith(`/ajustes/${tab.path}`)) ?? SETTINGS_TABS[0];
  const current = tab.path;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader crumbs={[{ label: t('settings.title'), to: '/ajustes' }, { label: t(tab.label) }]} title={t(tab.label)} />
      <Tabs value={current}>
        <TabsList className="flex-wrap">
          {SETTINGS_TABS.map((tab) => (
            <TabsTrigger key={tab.path} value={tab.path} asChild>
              <Link to={`/ajustes/${tab.path}`}>{t(tab.label)}</Link>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Outlet />
    </div>
  );
}
