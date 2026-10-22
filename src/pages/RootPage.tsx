import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import { SystemStatusCard } from '@/components/SystemStatusCard';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useMaterials, useSetActiveMaterial } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';

/** "/": to the active material's Panel; with no active one, the first
 *  material the user has (and it becomes the active one); with none, why. */
export function RootPage(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const materials = useMaterials();
  const setActive = useSetActiveMaterial();
  const activeId = me.data?.ui_preferences.active_material_id;
  const target = materials.data?.find((m) => m.id === activeId) ?? materials.data?.[0];
  const mustSave = target !== undefined && target.id !== activeId;
  useEffect(() => {
    if (mustSave && target) setActive.mutate(target.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per target
  }, [mustSave, target?.id]);
  useDocumentTitle(materials.data?.length === 0 ? t('material.noAccessTitle') : null);

  if (!materials.data) return <Skeleton className="h-40 w-full" />;
  if (target) return <Navigate to={`/materiales/${encodeURIComponent(target.id)}`} replace />;
  return (
    <div className="flex flex-col gap-6">
      <Card data-testid="no-material">
        <CardHeader>
          <CardTitle>{t('material.noAccessTitle')}</CardTitle>
          <CardDescription>{t('material.noAccess')}</CardDescription>
        </CardHeader>
      </Card>
      <SystemStatusCard />
    </div>
  );
}
