import { Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MaterialSelector } from '@/components/layout/MaterialSelector';
import { UserMenu } from '@/components/layout/UserMenu';
import { Button } from '@/components/ui/button';
import { useMe } from '@/hooks/useSession';
import { useAuthStore } from '@/stores/authStore';

const LOGO_SRC = '/brand/eme-group-logo.png';

export function AppHeader(): React.JSX.Element {
  const { t } = useTranslation();
  const status = useAuthStore((s) => s.status);
  const me = useMe();
  const ready = status === 'signedIn' && me.data !== undefined && !me.data.must_change_password;
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-4">
          <span className="rounded-md bg-logo-surface p-1">
            <img src={LOGO_SRC} alt={t('app.logoAlt')} className="h-9 w-auto" data-testid="brand-logo" />
          </span>
          <h1 className="text-lg font-semibold text-foreground sm:text-xl">{t('app.title')}</h1>
        </Link>
        {ready ? (
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <MaterialSelector />
            {me.data?.is_admin ? (
              <Button variant="ghost" asChild>
                <Link to="/ajustes" data-testid="settings-link">
                  <Settings aria-hidden="true" />
                  {t('header.settings')}
                </Link>
              </Button>
            ) : null}
            <UserMenu />
          </div>
        ) : null}
      </div>
    </header>
  );
}
