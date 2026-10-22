import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MaterialSelector } from '@/components/layout/MaterialSelector';
import { UserMenu } from '@/components/layout/UserMenu';
import { SidebarTrigger } from '@/components/ui/sidebar';

const LOGO_SRC = '/brand/eme-group-logo.png';

export function AppHeader({ withSidebar }: { withSidebar: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <header className="border-b bg-card">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        {withSidebar ? <SidebarTrigger data-testid="sidebar-trigger" /> : null}
        <Link to="/" className="flex items-center gap-4">
          <span className="rounded-md bg-logo-surface p-1">
            <img src={LOGO_SRC} alt={t('app.logoAlt')} className="h-9 w-auto" data-testid="brand-logo" />
          </span>
          <h1 className="text-lg font-semibold text-foreground sm:text-xl">{t('app.title')}</h1>
        </Link>
        {withSidebar ? (
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <MaterialSelector />
            <UserMenu />
          </div>
        ) : null}
      </div>
    </header>
  );
}
