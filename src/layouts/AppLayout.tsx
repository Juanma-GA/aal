import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { useSessionBootstrap } from '@/hooks/useSession';
import { useSystemTheme } from '@/hooks/useSystemTheme';
import { useUiStore } from '@/stores/uiStore';
import { AppHeader } from './AppHeader';

export function AppLayout(): React.JSX.Element {
  useSystemTheme();
  useSessionBootstrap();
  const { t } = useTranslation();
  useEffect(() => {
    document.title = t('app.title');
  }, [t]);
  // The sidebar itself arrives with E02 (PALI navigation); the layout already
  // reads its state from the UI store.
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  return (
    <div className="min-h-screen bg-background" data-sidebar-open={sidebarOpen}>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
      <Toaster position="bottom-right" />
    </div>
  );
}
