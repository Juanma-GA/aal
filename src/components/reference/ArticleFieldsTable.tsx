import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useArticleFields } from '@/hooks/useReferenceTables';

/** The 30 article fields (Fichero Carga / MAR06), read-only; a field's
 *  reference table links to it (`tablesBase`). */
export function ArticleFieldsTable({ tablesBase }: { tablesBase: string }): React.JSX.Element {
  const { t } = useTranslation();
  const fields = useArticleFields();
  if (!fields.data) return <Skeleton className="h-60 w-full" />;
  const none = t('reference.none');
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('articleFields.hint')}</p>
      <Table data-testid="article-fields">
        <TableHeader>
          <TableRow>
            <TableHead>{t('articleFields.prismaCode')}</TableHead>
            <TableHead>{t('articleFields.name')}</TableHead>
            <TableHead>{t('articleFields.importance')}</TableHead>
            <TableHead>{t('articleFields.guideField')}</TableHead>
            <TableHead>{t('articleFields.type')}</TableHead>
            <TableHead>{t('articleFields.length')}</TableHead>
            <TableHead>{t('articleFields.decimals')}</TableHead>
            <TableHead>{t('articleFields.relatedTo')}</TableHead>
            <TableHead>{t('articleFields.suppliedBy')}</TableHead>
            <TableHead>{t('articleFields.referenceTable')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fields.data.map((f) => (
            <TableRow key={f.prisma_code} data-testid={`field-row-${f.prisma_code}`}>
              <TableCell className="font-mono">{f.prisma_code}</TableCell>
              <TableCell className="whitespace-normal">{f.name}</TableCell>
              <TableCell>{f.importance}</TableCell>
              <TableCell>{f.guide_field}</TableCell>
              <TableCell>{f.data_type}</TableCell>
              <TableCell>{f.length ?? none}</TableCell>
              <TableCell>{f.decimals ?? none}</TableCell>
              <TableCell>{f.related_to ?? none}</TableCell>
              <TableCell className="whitespace-normal">{f.supplied_by_contractor}</TableCell>
              <TableCell>
                {f.reference_table_code ? (
                  <Link to={`${tablesBase}/${encodeURIComponent(f.reference_table_code)}`} className="text-primary hover:underline" title={f.reference_table_name ?? undefined}>
                    {f.reference_table_code}
                  </Link>
                ) : (
                  none
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
