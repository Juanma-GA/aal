import { useTranslation } from 'react-i18next';

const LOGO_SRC = '/brand/eme-group-logo.png';

export function AppHeader(): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3 sm:px-6">
        <span className="rounded-md bg-logo-surface p-1">
          <img src={LOGO_SRC} alt={t('app.logoAlt')} className="h-9 w-auto" data-testid="brand-logo" />
        </span>
        <h1 className="text-lg font-semibold text-foreground sm:text-xl">{t('app.title')}</h1>
      </div>
    </header>
  );
}
