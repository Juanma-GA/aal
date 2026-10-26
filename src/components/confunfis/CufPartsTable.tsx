// The CUF's "Tabla de partes" (E14, NT §9.1.10): the parts of every article
// in its CONFUNFIS, with their parent's positions and their total in the
// CUF. Read only: the parts are the article's, edited on its card.
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { PARTS_ANCHOR } from '@/components/articles/ArticleParts';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCufParts } from '@/hooks/useConfunfisExtras';
import { ARTICLES_PATH } from '@/pages/articles/ArticlePage';

export function CufPartsTable({ materialId }: { materialId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const parts = useCufParts(materialId);
  if (!parts.data) return <Skeleton className="h-64 w-full" />;
  return (
    <div className="flex flex-col gap-4" data-testid="confunfis-parts">
      <div className="flex flex-wrap items-center gap-2">
        <Badge data-testid="cuf-parts-count">{t('confunfis.parts.count', { count: parts.data.length })}</Badge>
        <p className="text-sm text-muted-foreground">{t('confunfis.parts.hint')}</p>
      </div>
      {parts.data.length === 0 ? <p className="text-sm text-muted-foreground">{t('confunfis.parts.empty')}</p> : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('confunfis.parts.parent')}</TableHead>
                <TableHead className="w-16">{t('articles.parts.cop')}</TableHead>
                <TableHead className="w-16">{t('articles.parts.alp')}</TableHead>
                <TableHead>{t('articles.parts.part')}</TableHead>
                <TableHead className="w-24">{t('articles.parts.quantity')}</TableHead>
                <TableHead className="w-24">{t('confunfis.fields.total')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {parts.data.map((p) => (
                <TableRow key={p.id} data-testid={`cuf-part-${p.parent.id}-${p.cop}-${p.alp}`}>
                  <TableCell>
                    <Link to={`${ARTICLES_PATH}/${p.parent.id}#${PARTS_ANCHOR}`} className="text-link underline-offset-2 hover:underline">{p.parent.nombre}</Link>
                    <span className="block font-mono text-xs text-muted-foreground">{p.parent_positions.join(' · ')}</span>
                  </TableCell>
                  <TableCell className="font-mono">{p.cop}</TableCell>
                  <TableCell className="font-mono">{p.alp}</TableCell>
                  <TableCell>
                    {p.article ? <Link to={`${ARTICLES_PATH}/${p.article.id}`} className="text-link underline-offset-2 hover:underline">{p.article.nombre || p.part_name}</Link> : (p.part_name ?? '—')}
                    <span className="block font-mono text-xs text-muted-foreground">{[p.article?.noc, p.article?.pn].filter(Boolean).join(' · ')}</span>
                    {p.observation_codes.length ? (
                      <span className="flex flex-wrap gap-1">
                        {p.observation_codes.map((c) => <Badge key={c} variant="outline" className="border-warning text-warning">{t(`confunfis.observations.${c}.short`)}</Badge>)}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell>{p.quantity ?? '—'}</TableCell>
                  <TableCell data-testid={`cuf-part-total-${p.parent.id}-${p.cop}-${p.alp}`}>{p.total ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
