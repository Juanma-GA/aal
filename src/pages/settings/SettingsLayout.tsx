import { useTranslation } from 'react-i18next';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const SETTINGS_TABS = [
  { path: 'usuarios', label: 'settings.tabs.users' },
  { path: 'materiales', label: 'settings.tabs.materials' },
  { path: 'roles', label: 'settings.tabs.roles' },
  { path: 'auditoria', label: 'settings.tabs.audit' },
  { path: 'parametros', label: 'settings.tabs.parameters' },
] as const;

export function SettingsLayout(): React.JSX.Element {
  const { t } = useTranslation();
  const location = useLocation();
  const current = SETTINGS_TABS.find((tab) => location.pathname.startsWith(`/ajustes/${tab.path}`))?.path ?? 'usuarios';
  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-2xl font-semibold text-foreground">{t('settings.title')}</h2>
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
