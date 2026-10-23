import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { NavRow } from '@/components/layout/NavRow';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useReferenceTables } from '@/hooks/useReferenceTables';

/** The 15 reference tables with their source and number of values. */
export function ReferenceTablesList({ base }: { base: string }): React.JSX.Element {
  const { t } = useTranslation();
  const tables = useReferenceTables();
  if (!tables.data) return <Skeleton className="h-60 w-full" />;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('reference.hint')}</p>
      <Table data-testid="reference-tables">
        <TableHeader>
          <TableRow>
            <TableHead>{t('reference.code')}</TableHead>
            <TableHead>{t('reference.name')}</TableHead>
            <TableHead>{t('reference.source')}</TableHead>
            <TableHead className="text-right">{t('reference.values')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.open')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tables.data.map((table) => (
            <NavRow
              key={table.code}
              to={`${base}/${encodeURIComponent(table.code)}`}
              label={t('reference.openTable', { code: table.code })}
              data-testid={`reference-row-${table.code}`}
            >
              <TableCell className="font-mono">
                <Link to={`${base}/${encodeURIComponent(table.code)}`} className="text-link underline-offset-2 hover:underline">
                  {table.code}
                </Link>
              </TableCell>
              <TableCell className="whitespace-normal">{table.name}</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground">{table.source}</TableCell>
              <TableCell className="text-right" data-testid="reference-count">
                {t('reference.valuesCount', { active: table.active_count, total: table.value_count })}
              </TableCell>
            </NavRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
