import { useTranslation } from 'react-i18next';
import { NavRow } from '@/components/layout/NavRow';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { CatalogVersion } from '@/types/catalog';

/** Every imported version; a row opens it. */
export function VersionsTable({ versions, current, onOpen }: {
  versions: CatalogVersion[];
  current: string;
  onOpen: (id: string) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <Table data-testid="catalog-versions">
      <TableHeader>
        <TableRow>
          <TableHead>{t('catalog.version')}</TableHead>
          <TableHead>{t('catalog.file')}</TableHead>
          <TableHead>{t('catalog.importedAt')}</TableHead>
          <TableHead>{t('catalog.importedBy')}</TableHead>
          <TableHead className="text-right">{t('catalog.sns')}</TableHead>
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
          </NavRow>
        ))}
      </TableBody>
    </Table>
  );
}
