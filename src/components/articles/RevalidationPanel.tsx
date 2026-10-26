import { RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useLatestRevalidation, useStartRevalidation } from '@/hooks/useArticles';
import { AR_RULES, type Revalidation } from '@/types/articles';

function reasonText(t: (key: string, o?: Record<string, unknown>) => string, run: Revalidation): string {
  return t(`articles.revalidation.reasons.${run.reason}`, { table: run.detail.table ?? '', field: run.detail.field ?? '' });
}

/** The admin's "Revalidar todos los artículos" (E13) and where the last run
 *  stands -- the button's, or the one an import or edit of a reference table
 *  or a field definition started: running, or what appeared and disappeared
 *  by rule. */
export function RevalidationPanel(): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const latest = useLatestRevalidation();
  const start = useStartRevalidation();
  const [open, setOpen] = useState(false);
  const run = latest.data ?? null;
  const running = run !== null && (run.status === 'queued' || run.status === 'running');
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  const totals = run?.report
    ? AR_RULES.reduce((acc, r) => ({ appeared: acc.appeared + (run.report?.by_rule[r]?.appeared ?? 0), disappeared: acc.disappeared + (run.report?.by_rule[r]?.disappeared ?? 0) }), { appeared: 0, disappeared: 0 })
    : null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2 text-sm" data-testid="revalidation-panel">
      <Button variant="outline" size="sm" disabled={running || start.isPending} onClick={() => start.mutate()} data-testid="revalidate-all">
        <RefreshCw aria-hidden="true" className={running ? 'animate-spin' : undefined} />
        {t('articles.revalidation.button')}
      </Button>
      <p className="text-muted-foreground" data-testid="revalidation-status" role="status">
        {run === null
          ? t('articles.revalidation.never')
          : running
            ? t('articles.revalidation.running', { reason: reasonText(t, run) })
            : run.status === 'failed'
              ? t('articles.revalidation.failed', { when: when(run.created_at) })
              : t('articles.revalidation.done', { when: when(run.finished_at ?? run.created_at), reason: reasonText(t, run), appeared: totals?.appeared ?? 0, disappeared: totals?.disappeared ?? 0 })}
      </p>
      {run?.status === 'done' && run.report ? (
        <button type="button" className="text-link underline-offset-2 hover:underline" onClick={() => setOpen(true)} data-testid="revalidation-report-open">
          {t('articles.revalidation.seeReport')}
        </button>
      ) : null}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="revalidation-report">
          <DialogHeader>
            <DialogTitle>{t('articles.revalidation.reportTitle')}</DialogTitle>
            <DialogDescription>
              {run?.report ? t('articles.revalidation.reportHint', { count: run.report.articles, changed: run.report.changed, reason: reasonText(t, run) }) : null}
            </DialogDescription>
          </DialogHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('articles.revalidation.rule')}</TableHead>
                <TableHead className="text-right">{t('articles.revalidation.appeared')}</TableHead>
                <TableHead className="text-right">{t('articles.revalidation.disappeared')}</TableHead>
                <TableHead className="text-right">{t('articles.revalidation.now')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {AR_RULES.map((rule) => {
                const r = run?.report?.by_rule[rule];
                return (
                  <TableRow key={rule} data-testid={`revalidation-rule-${rule}`}>
                    <TableCell>
                      <span className="font-mono">{rule}</span> · {t(`articles.rules.${rule}.title`)}
                    </TableCell>
                    <TableCell className="text-right">{r?.appeared ?? 0}</TableCell>
                    <TableCell className="text-right">{r?.disappeared ?? 0}</TableCell>
                    <TableCell className="text-right">{r?.now ?? 0}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DialogContent>
      </Dialog>
    </div>
  );
}
