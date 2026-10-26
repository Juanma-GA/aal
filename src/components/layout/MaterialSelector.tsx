import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useActiveMaterial, useMaterials, useSetActiveMaterial } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';
import { catalogLabel } from '@/lib/labels';
import { notifyError } from '@/lib/notify';

/** The materials the user is assigned to, with their role. Choosing one
 *  goes to its URL and saves it as the active material in the user's
 *  preferences on the server (HR1). */
export function MaterialSelector(): React.JSX.Element | null {
  const { t } = useTranslation();
  const me = useMe();
  const materials = useMaterials();
  const active = useActiveMaterial();
  const setActive = useSetActiveMaterial();
  const navigate = useNavigate();
  const location = useLocation();
  // Another material keeps the page the user is on (its Panel or the same
  // module card); outside a material, its Panel.
  const choose = (id: string) => {
    setActive.mutate(id, { onError: (error) => notifyError(error, t) });
    const inMaterial = location.pathname.match(/^\/materiales\/[^/]+(\/.*)?$/);
    navigate(`/materiales/${encodeURIComponent(id)}${inMaterial?.[1] ?? ''}`);
  };
  if (!materials.data) return null;
  if (materials.data.length === 0) {
    return <span className="text-sm text-header-control-foreground">{t('header.noMaterials')}</span>;
  }
  const roleLabel = (role: string | null) => (role ? catalogLabel(t, 'roles', role) : me.data?.is_admin ? t('header.admin') : '');
  return (
    <div className="flex items-center gap-2">
      <Select
        value={active?.id ?? ''}
        onValueChange={choose}
      >
        <SelectTrigger className="w-56 bg-card text-card-foreground sm:w-72" aria-label={t('header.material')} data-testid="material-selector">
          <SelectValue placeholder={t('header.chooseMaterial')} />
        </SelectTrigger>
        <SelectContent>
          {materials.data.map((m) => (
            <SelectItem key={m.id} value={m.id}>
              {m.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {active ? (
        <Badge variant="secondary" data-testid="material-role">
          {roleLabel(active.role)}
        </Badge>
      ) : null}
    </div>
  );
}
