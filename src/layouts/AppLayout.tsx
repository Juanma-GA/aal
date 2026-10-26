import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { Toaster } from '@/components/ui/sonner';
import { useMe, useSessionBootstrap } from '@/hooks/useSession';
import { useSidebarLayout } from '@/hooks/useSidebarLayout';
import { useSystemTheme } from '@/hooks/useSystemTheme';
import { useAuthStore } from '@/stores/authStore';
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
  const layout = useSidebarLayout();
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
    <SidebarProvider open={layout.open} onOpenChange={layout.setOpen} style={{ '--sidebar-width': `${layout.width}px` } as React.CSSProperties}>
      {/* The sidebar goes before the content on the left, after it on the right. */}
      {layout.side === 'left' ? <AppSidebar layout={layout} /> : null}
      <SidebarInset className="min-w-0 bg-background">
        <AppHeader withSidebar />
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
      </SidebarInset>
      {layout.side === 'right' ? <AppSidebar layout={layout} /> : null}
      <Toaster position="bottom-right" />
    </SidebarProvider>
  );
}
