import { useQuery } from '@tanstack/react-query';
import { Check, Minus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { catalogLabel } from '@/lib/labels';
import { fetchRoles } from '@/services/adminApi';

/** The seeded matrix, read-only in this version. */
export function RolesTab(): React.JSX.Element {
  const { t } = useTranslation();
  const roles = useQuery({ queryKey: ['roles'], queryFn: fetchRoles });
  if (!roles.data) return <Skeleton className="h-60 w-full" />;
  const { matrix } = roles.data;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('settings.roles.hint')}</p>
      <Table data-testid="roles-matrix">
        <TableHeader>
          <TableRow>
            <TableHead>{t('settings.roles.permission')}</TableHead>
            {roles.data.roles.map((r) => (
              <TableHead key={r.code} className="text-center">
                {catalogLabel(t, 'roles', r.code)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {roles.data.permissions.map((p) => (
            <TableRow key={p.code}>
              <TableCell>
                <span className="block text-foreground">{catalogLabel(t, 'permissions', p.code)}</span>
                <span className="block text-xs text-muted-foreground">{catalogLabel(t, 'areas', p.area)}</span>
              </TableCell>
              {roles.data.roles.map((r) => {
                const allowed = matrix[r.code]?.includes(p.code) ?? false;
                return (
                  <TableCell key={r.code} className="text-center">
                    {allowed ? (
                      <Check className="mx-auto size-4 text-success" aria-label={t('settings.roles.allowed')} />
                    ) : (
                      <Minus className="mx-auto size-4 text-muted-foreground" aria-label={t('settings.roles.denied')} />
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-sm text-muted-foreground">{t('settings.roles.adminNote')}</p>
    </div>
  );
}
