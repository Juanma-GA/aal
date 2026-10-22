import { useEffect } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { useMaterials, useSetActiveMaterial } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';
import { NotFoundPage } from '@/pages/NotFoundPage';

/** The pages of one material: /materiales/:materialId/... A material the
 *  user cannot see is the humanized 404. Opening one by its URL makes it
 *  the active material (saved on the server, HR1). */
export function MaterialLayout(): React.JSX.Element {
  const { materialId } = useParams();
  const me = useMe();
  const materials = useMaterials();
  const setActive = useSetActiveMaterial();
  const material = materials.data?.find((m) => m.id === materialId);
  const activeId = me.data?.ui_preferences.active_material_id;
  useEffect(() => {
    if (material && material.id !== activeId) setActive.mutate(material.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when the URL's material changes
  }, [material?.id]);

  if (!materials.data) return <Skeleton className="h-40 w-full" />;
  if (!material) return <NotFoundPage kind="material" />;
  return <Outlet context={material} />;
}
