import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { Toaster } from '@/components/ui/sonner';
import { useMe, useSessionBootstrap } from '@/hooks/useSession';
import { useSystemTheme } from '@/hooks/useSystemTheme';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { AppHeader } from './AppHeader';

/** The shell: header, and -- once signed in -- the PALI sidebar. */
export function AppLayout(): React.JSX.Element {
  useSystemTheme();
  useSessionBootstrap();
  const { t } = useTranslation();
  useEffect(() => {
    document.title = t('app.title');
  }, [t]);
  const status = useAuthStore((s) => s.status);
  const me = useMe();
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen);
  const ready = status === 'signedIn' && me.data !== undefined && !me.data.must_change_password;

  if (!ready) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader withSidebar={false} />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
        <Toaster position="bottom-right" />
      </div>
    );
  }
  return (
    <SidebarProvider open={sidebarOpen} onOpenChange={setSidebarOpen}>
      <AppSidebar />
      <SidebarInset className="min-w-0 bg-background">
        <AppHeader withSidebar />
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
      </SidebarInset>
      <Toaster position="bottom-right" />
    </SidebarProvider>
  );
}
