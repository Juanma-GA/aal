import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useActiveMaterial, useMaterials } from '@/hooks/useMaterials';
import { useMe } from '@/hooks/useSession';
import { catalogLabel } from '@/lib/labels';

const FIELDS = ['noc', 'part_number', 'ncage'] as const;

/** The active material: its data, the user's role on it and what they may
 *  do. With no material, why and what to do about it. */
export function MaterialCard(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const materials = useMaterials();
  const active = useActiveMaterial();

  if (!materials.data) {
    return (
      <Card>
        <CardContent className="flex flex-col gap-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-5 w-full" />
        </CardContent>
      </Card>
    );
  }
  if (materials.data.length === 0) {
    return (
      <Card data-testid="no-material">
        <CardHeader>
          <CardTitle>{t('material.noAccessTitle')}</CardTitle>
          <CardDescription>{t('material.noAccess')}</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  if (!active) {
    return (
      <Card data-testid="no-material">
        <CardHeader>
          <CardTitle>{t('material.chooseTitle')}</CardTitle>
          <CardDescription>{t('material.choose')}</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  return (
    <Card data-testid="active-material">
      <CardHeader>
        <CardDescription>{t('material.activeTitle')}</CardDescription>
        <CardTitle className="text-xl">{active.name}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {active.description ? <p className="text-sm text-foreground">{active.description}</p> : null}
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {FIELDS.map((field) => (
            <div key={field}>
              <dt className="text-sm text-muted-foreground">{t(`material.fields.${field}`)}</dt>
              <dd className="font-mono text-sm text-foreground">{active[field] ?? t('material.empty')}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-col gap-2">
          <span className="text-sm text-muted-foreground">{t('material.yourRole')}</span>
          <div>
            <Badge variant="secondary">{active.role ? catalogLabel(t, 'roles', active.role) : t('material.adminRole')}</Badge>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-sm text-muted-foreground">{t('material.yourPermissions')}</span>
          <ul className="flex flex-wrap gap-2" data-testid="material-permissions">
            {active.permissions.map((code) => (
              <li key={code}>
                <Badge variant="outline">{catalogLabel(t, 'permissions', code)}</Badge>
              </li>
            ))}
          </ul>
        </div>
        {me.data?.is_admin ? (
          <div>
            <Button variant="outline" asChild>
              <Link to="/ajustes/materiales">{t('material.editInSettings')}</Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
