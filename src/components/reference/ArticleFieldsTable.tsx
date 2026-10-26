import { Info, Pencil } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useArticleFields } from '@/hooks/useReferenceTables';
import type { ArticleField } from '@/types/reference';
import { FieldDefinitionDialog } from './FieldDefinitionDialog';

/** "Carácter · 13", "Numérico · 9,2". */
function typeText(f: ArticleField): string {
  if (f.length === null) return f.data_type;
  return `${f.data_type} · ${f.length}${f.decimals ? `,${f.decimals}` : ''}`;
}

/** The 30 article fields (Fichero Carga / MAR06), compact (no horizontal
 *  scroll on a desktop): the name wraps, the type carries its length, the
 *  guide field and the rest are in each row's detail; a field's reference
 *  table links to it (`tablesBase`). `editable` (Ajustes, the admin, E13):
 *  each row opens its definition to correct it. */
export function ArticleFieldsTable({ tablesBase, editable = false }: { tablesBase: string; editable?: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const fields = useArticleFields();
  const [editing, setEditing] = useState<ArticleField | null>(null);
  if (!fields.data) return <Skeleton className="h-60 w-full" />;
  const none = t('reference.none');
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('articleFields.hint')}</p>
      <Table data-testid="article-fields" className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">{t('articleFields.prismaCode')}</TableHead>
            <TableHead>{t('articleFields.name')}</TableHead>
            <TableHead className="w-28">{t('articleFields.importance')}</TableHead>
            <TableHead className="w-36">{t('articleFields.type')}</TableHead>
            <TableHead className="w-40">{t('articleFields.referenceTable')}</TableHead>
            <TableHead className={editable ? 'w-20' : 'w-12'}>
              <span className="sr-only">{t('articleFields.detail')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fields.data.map((f) => (
            <TableRow key={f.prisma_code} data-testid={`field-row-${f.prisma_code}`}>
              <TableCell className="font-mono text-xs">{f.prisma_code}</TableCell>
              <TableCell className="whitespace-normal">
                {f.name}
                {f.edited_by_admin ? <Badge variant="outline" className="ml-2" data-testid={`field-edited-${f.prisma_code}`}>{t('articleFields.edited')}</Badge> : null}
              </TableCell>
              <TableCell className="whitespace-normal">{f.importance}</TableCell>
              <TableCell className="whitespace-normal">{typeText(f)}</TableCell>
              <TableCell className="whitespace-normal">
                {f.reference_table_code ? (
                  <Link to={`${tablesBase}/${encodeURIComponent(f.reference_table_code)}`} className="text-link underline-offset-2 hover:underline">
                    <span className="font-mono">{f.reference_table_code}</span>
                    {f.reference_table_name ? <span className="block text-xs">{f.reference_table_name}</span> : null}
                  </Link>
                ) : (
                  none
                )}
              </TableCell>
              <TableCell>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" className="inline-flex size-6 items-center justify-center rounded text-muted-foreground hover:text-foreground" aria-label={t('articleFields.detailOf', { code: f.prisma_code })}>
                      <Info className="size-4" aria-hidden="true" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs">
                      <dt>{t('articleFields.guideField')}</dt>
                      <dd>{f.guide_field}</dd>
                      <dt>{t('articleFields.relatedTo')}</dt>
                      <dd>{f.related_to ?? none}</dd>
                      <dt>{t('articleFields.suppliedBy')}</dt>
                      <dd>{f.supplied_by_contractor}</dd>
                    </dl>
                  </TooltipContent>
                </Tooltip>
                {editable ? (
                  <Button variant="ghost" size="icon" className="size-6" aria-label={t('articleFields.editOf', { code: f.prisma_code })} onClick={() => setEditing(f)} data-testid={`field-edit-${f.prisma_code}`}>
                    <Pencil className="size-4" aria-hidden="true" />
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {editing ? <FieldDefinitionDialog field={editing} onOpenChange={(open) => { if (!open) setEditing(null); }} /> : null}
    </div>
  );
}
