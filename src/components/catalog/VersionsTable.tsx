import { MoreHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavRow } from '@/components/layout/NavRow';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useActivateCatalogVersion, useDeleteCatalogVersion } from '@/hooks/useCatalogVersions';
import type { CatalogVersion } from '@/types/catalog';

/** Every imported version; a row opens it. An admin activates an older one
 *  or deletes one (never the active one, nor one a CUF works with: the
 *  server says which CUF). */
export function VersionsTable({ versions, current, onOpen, isAdmin }: {
  versions: CatalogVersion[];
  current: string;
  onOpen: (id: string) => void;
  isAdmin: boolean;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState<{ action: 'activate' | 'delete'; version: CatalogVersion } | null>(null);
  const remove = useDeleteCatalogVersion();
  const activate = useActivateCatalogVersion();
  const label = (v: CatalogVersion) => t('catalog.versionLabel', { number: v.number, label: v.label });
  return (
    <>
      <Table data-testid="catalog-versions">
        <TableHeader>
          <TableRow>
            <TableHead>{t('catalog.version')}</TableHead>
            <TableHead>{t('catalog.file')}</TableHead>
            <TableHead>{t('catalog.importedAt')}</TableHead>
            <TableHead>{t('catalog.importedBy')}</TableHead>
            <TableHead className="text-right">{t('catalog.sns')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.more')}</span>
            </TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.open')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {versions.map((v) => (
            <NavRow
              key={v.id}
              onOpen={() => onOpen(v.id)}
              label={t('catalog.openVersion', { number: v.number })}
              data-testid={`version-row-${v.number}`}
              className={v.id === current ? 'bg-accent' : undefined}
            >
              <TableCell>
                <button type="button" className="text-link underline-offset-2 hover:underline" onClick={() => onOpen(v.id)}>
                  {t('catalog.versionLabel', { number: v.number, label: v.label })}
                </button>
                {v.is_active ? (
                  <Badge variant="secondary" className="ml-2">
                    {t('catalog.active')}
                  </Badge>
                ) : null}
              </TableCell>
              <TableCell className="font-mono text-xs">{v.file_name}</TableCell>
              <TableCell>{new Date(v.imported_at).toLocaleString('es-ES')}</TableCell>
              <TableCell>{v.imported_by ?? t('settings.audit.removedUser')}</TableCell>
              <TableCell className="text-right">{v.counts.sns ?? 0}</TableCell>
              <TableCell className="w-10">
                {isAdmin ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={t('actions.more')} data-testid={`version-menu-${v.number}`}>
                        <MoreHorizontal aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem disabled={v.is_active} onSelect={() => setConfirming({ action: 'activate', version: v })} data-testid={`activate-version-${v.number}`}>
                        {t('catalog.activateVersion')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        disabled={v.is_active}
                        onSelect={() => setConfirming({ action: 'delete', version: v })}
                        data-testid={`delete-version-${v.number}`}
                      >
                        {t('catalog.deleteVersion')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : null}
              </TableCell>
            </NavRow>
          ))}
        </TableBody>
      </Table>
      {isAdmin && versions.some((v) => v.is_active) ? <p className="mt-2 text-xs text-muted-foreground">{t('catalog.activeNotDeleted')}</p> : null}
      <ConfirmDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={
          confirming?.action === 'delete'
            ? t('catalog.deleteVersionTitle', { version: confirming ? label(confirming.version) : '' })
            : t('catalog.activateVersionTitle', { version: confirming ? label(confirming.version) : '' })
        }
        description={confirming?.action === 'delete' ? t('catalog.deleteVersionHint') : t('catalog.activateVersionHint')}
        confirmLabel={confirming?.action === 'delete' ? t('catalog.deleteVersion') : t('catalog.activateVersion')}
        onConfirm={() => {
          if (!confirming) return;
          if (confirming.action === 'delete') remove.mutate(confirming.version);
          else activate.mutate(confirming.version);
          setConfirming(null);
        }}
      />
    </>
  );
}
