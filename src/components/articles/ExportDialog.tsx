import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { exportArticles, fetchExportSummary } from '@/services/articlesApi';
import { AR_RULES, type ArticleFilters, type ArticleTemplate } from '@/types/articles';

/** Before exporting: how many articles go and how many break an AR rule.
 *  Exporting is not blocked in E12 (the SIGLE package will block it). */
export function ExportDialog({ template, filters, onOpenChange }: {
  template: ArticleTemplate | null;
  filters: ArticleFilters;
  onOpenChange: (open: boolean) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  const summary = useQuery({ queryKey: ['articles', 'export-summary', filters], queryFn: () => fetchExportSummary(filters), enabled: template !== null });
  const run = () => {
    if (!template) return;
    exportArticles(template, filters)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? `${template}.xlsx`))
      .catch((error: unknown) => notifyError(error, t));
    onOpenChange(false);
  };
  const data = summary.data;
  return (
    <Dialog open={template !== null} onOpenChange={onOpenChange}>
      <DialogContent data-testid="article-export">
        <DialogHeader>
          <DialogTitle>{template ? t(`articles.templates.${template}`) : ''}</DialogTitle>
          <DialogDescription>{t('articles.exportHint')}</DialogDescription>
        </DialogHeader>
        {!data ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="flex flex-col gap-2 text-sm" data-testid="article-export-summary">
            <p>{t('articles.exportCount', { count: data.articles, withFindings: data.with_findings })}</p>
            <div className="flex flex-wrap gap-1">
              {AR_RULES.filter((r) => data.by_rule[r]).map((r) => (
                <Badge key={r} variant="outline">
                  {r}: {data.by_rule[r]}
                </Badge>
              ))}
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('actions.cancel')}
          </Button>
          <Button disabled={!data || data.articles === 0} onClick={run} data-testid="article-export-run">
            {t('articles.export')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
