// Route guards. They only decide what to show: every action is checked
// again by the server (app/api/deps.py).
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { useMaterialPermission } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';
import { useAuthStore } from '@/stores/authStore';

export const CHANGE_PASSWORD_PATH = '/cambiar-contrasena';

function PageSkeleton(): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3" role="status" aria-live="polite">
      <span className="sr-only">{t('auth.checkingSession')}</span>
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/** Signed in; with a pending password change, only the change page. */
export function RequireAuth(): React.JSX.Element {
  const status = useAuthStore((s) => s.status);
  const me = useMe();
  const location = useLocation();
  if (status === 'checking') return <PageSkeleton />;
  if (status === 'signedOut') return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!me.data) return <PageSkeleton />;
  if (me.data.must_change_password && location.pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />;
  }
  return <Outlet />;
}

/** A global admin. */
export function RequireAdmin(): React.JSX.Element {
  const me = useMe();
  if (!me.data) return <PageSkeleton />;
  return me.data.is_admin ? <Outlet /> : <Navigate to="/" replace />;
}

/** A permission on the active material (for the pages of E02 onwards). */
export function RequireMaterialPermission({ permission }: { permission: string }): React.JSX.Element {
  return useMaterialPermission(permission) ? <Outlet /> : <Navigate to="/" replace />;
}
