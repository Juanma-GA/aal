import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useActiveMaterial, useMaterials, useSetActiveMaterial } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';
import { catalogLabel } from '@/lib/labels';
import { notifyError } from '@/lib/notify';

/** The materials the user is assigned to, with their role; the choice is
 *  saved in the user's preferences on the server (HR1). */
export function MaterialSelector(): React.JSX.Element | null {
  const { t } = useTranslation();
  const me = useMe();
  const materials = useMaterials();
  const active = useActiveMaterial();
  const setActive = useSetActiveMaterial();
  if (!materials.data) return null;
  if (materials.data.length === 0) {
    return <span className="text-sm text-muted-foreground">{t('header.noMaterials')}</span>;
  }
  const roleLabel = (role: string | null) => (role ? catalogLabel(t, 'roles', role) : me.data?.is_admin ? t('header.admin') : '');
  return (
    <div className="flex items-center gap-2">
      <Select
        value={active?.id ?? ''}
        onValueChange={(id) => setActive.mutate(id, { onError: (error) => notifyError(error, t) })}
      >
        <SelectTrigger className="w-56 sm:w-72" aria-label={t('header.material')} data-testid="material-selector">
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
