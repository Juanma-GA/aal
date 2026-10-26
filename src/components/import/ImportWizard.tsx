// The two phases of an Excel import (E03), for any template: upload the
// file, wait while the server analyses it (polling the job, Postgres is the
// only record of where it stands: HR1), review the report and apply it.
// E10 (CONF_FUN), E12 (Fichero Carga) and E15 (Anexo XI) use it as it is,
// with their own `start`.
import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChangeValue, RowsDiff } from '@/components/import/ChangeDetail';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { findingText } from '@/lib/articleText';
import { humanize } from '@/lib/humanize';
import { notifyError } from '@/lib/notify';
import { describeApiError } from '@/services/apiErrors';
import { applyImportJob, fetchImportJob } from '@/services/importsApi';
import type { ImportIssue, ImportJob, ImportReport } from '@/types/imports';

const POLL_MS = 1000;
// Rows per page of a report tab: a first real CONF_FUN import has thousands
// of new SNS, and the whole list is still there page by page (HR6).
const PAGE_SIZE = 200;
const TABS = ['new', 'modified', 'unchanged', 'removed', 'rejected', 'ar', 'corrections', 'errors', 'warnings'] as const;
// Tabs only some templates have (their part of the report is absent otherwise).
const OPTIONAL: Partial<Record<Tab, keyof ImportReport>> = { removed: 'removed', rejected: 'rejected', ar: 'ar', corrections: 'corrections' };
type Tab = (typeof TABS)[number];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Phase 1: uploads the file and returns the job being analysed. */
  start: (file: File) => Promise<ImportJob>;
  /** After applying: refresh what the import changed. */
  onApplied?: (job: ImportJob) => void;
  /** Articles (E12): PRISMA code -> field name, for the AR findings. */
  fieldNames?: Record<string, string>;
}

/** One page of `items`, and the controls to move (none for a single page). */
function usePage<T>(items: T[]): [T[], React.ReactNode] {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const controls =
    pages > 1 ? (
      <div className="flex items-center justify-end gap-2 py-2 text-sm">
        <Button size="sm" variant="outline" disabled={current === 0} onClick={() => setPage(current - 1)}>
          {t('actions.previous')}
        </Button>
        {t('import.page', { page: current + 1, pages, total: items.length })}
        <Button size="sm" variant="outline" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
          {t('actions.next')}
        </Button>
      </div>
    ) : null;
  return [items.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE), controls];
}

function useIssueText() {
  const { t } = useTranslation();
  return (issue: ImportIssue) => t(`import.issues.${issue.code}`, { ...issue.params, defaultValue: '' }) || humanize(issue.code);
}

function Issues({ issues, testId }: { issues: ImportIssue[]; testId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const text = useIssueText();
  const [shown, controls] = usePage(issues);
  if (issues.length === 0) return <p className="py-4 text-sm text-muted-foreground">{t('import.nothing')}</p>;
  return (
    <>
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{t('import.where')}</TableHead>
          <TableHead>{t('import.field')}</TableHead>
          <TableHead>{t('import.message')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {shown.map((issue, i) => (
          <TableRow key={`${issue.row ?? 0}-${issue.column ?? ''}-${issue.code}-${i}`}>
            <TableCell className="whitespace-nowrap">
              {issue.row === null
                ? t('import.fileLevel')
                : issue.column
                  ? t('import.cell', { row: issue.row, column: issue.column })
                  : t('import.rowOnly', { row: issue.row })}
            </TableCell>
            <TableCell>{issue.header ?? t('reference.none')}</TableCell>
            <TableCell className="whitespace-normal">{text(issue)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    {controls}
    </>
  );
}

function Report({ report, counts, fieldNames }: { report: ImportReport; counts: ImportJob['counts']; fieldNames: Record<string, string> }): React.JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>(
    counts.errors ? 'errors' : counts.rejected ? 'rejected' : counts.modified ? 'modified' : counts.new ? 'new' : 'unchanged',
  );
  const valueColumns = report.columns.filter((c) => c.field !== report.columns[0]?.field);
  const empty = <p className="py-4 text-sm text-muted-foreground">{t('import.nothing')}</p>;
  const [newRows, newPages] = usePage(report.new);
  const [modifiedRows, modifiedPages] = usePage(report.modified);
  const [unchangedRows, unchangedPages] = usePage(report.unchanged);
  const [removedRows, removedPages] = usePage(report.removed ?? []);
  const [rejectedRows, rejectedPages] = usePage(report.rejected ?? []);
  const [correctionRows, correctionPages] = usePage(report.corrections ?? []);
  const issueText = useIssueText();
  const arRules = Object.entries(report.ar ?? {});
  const badge = (name: Tab) => (name === 'ar' ? arRules.reduce((n, [, items]) => n + new Set(items.map((i) => i.row)).size, 0) : (counts[name] ?? 0));
  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
      <TabsList className="flex-wrap">
        {TABS.filter((name) => !OPTIONAL[name] || report[OPTIONAL[name]]).map((name) => (
          <TabsTrigger key={name} value={name} data-testid={`import-tab-${name}`}>
            {t(`import.tabs.${name}`)}
            <Badge variant={(name === 'errors' && counts.errors) || (name === 'rejected' && counts.rejected) ? 'destructive' : 'secondary'} data-testid={`import-count-${name}`}>
              {badge(name)}
            </Badge>
          </TabsTrigger>
        ))}
      </TabsList>
      <div className="max-h-80 overflow-auto">
        <TabsContent value="new">
          {report.new.length === 0 ? empty : (
            <Table data-testid="import-new">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.row')}</TableHead>
                  <TableHead>{t('import.key')}</TableHead>
                  {valueColumns.map((c) => <TableHead key={c.field}>{c.header}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {newRows.map((row) => (
                  <TableRow key={row.row}>
                    <TableCell>{row.row}</TableCell>
                    <TableCell className="font-mono">{row.key}</TableCell>
                    {valueColumns.map((c) => <TableCell key={c.field} className="whitespace-normal">{row.values[c.field] ?? ''}</TableCell>)}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {newPages}
        </TabsContent>
        <TabsContent value="modified">
          {report.modified.length === 0 ? empty : (
            <Table data-testid="import-modified">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.row')}</TableHead>
                  <TableHead>{t('import.key')}</TableHead>
                  <TableHead>{t('import.field')}</TableHead>
                  <TableHead>{t('import.before')}</TableHead>
                  <TableHead>{t('import.after')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {modifiedRows.flatMap((row) =>
                  row.changes.map((change, i) => (
                    <TableRow key={`${row.row}-${change.field}`}>
                      <TableCell>{i === 0 ? row.row : ''}</TableCell>
                      <TableCell className="font-mono">{i === 0 ? row.key : ''}</TableCell>
                      <TableCell>{change.header}</TableCell>
                      {change.field === 'rows' && row.rows ? (
                        <TableCell colSpan={2} className="whitespace-normal">
                          <RowsDiff rows={row.rows} />
                        </TableCell>
                      ) : (
                        <>
                          <TableCell className="whitespace-normal text-muted-foreground line-through">
                            <ChangeValue change={change} side="before" />
                          </TableCell>
                          <TableCell className="whitespace-normal">
                            <ChangeValue change={change} side="after" />
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  )),
                )}
              </TableBody>
            </Table>
          )}
          {modifiedPages}
        </TabsContent>
        <TabsContent value="unchanged">
          {report.unchanged.length === 0 ? empty : (
            <Table data-testid="import-unchanged">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.row')}</TableHead>
                  <TableHead>{t('import.key')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {unchangedRows.map((row) => (
                  <TableRow key={row.row}>
                    <TableCell>{row.row}</TableCell>
                    <TableCell className="font-mono">{row.key}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {unchangedPages}
        </TabsContent>
        <TabsContent value="removed">
          {!report.removed?.length ? empty : (
            <Table data-testid="import-removed">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.key')}</TableHead>
                  {valueColumns.map((c) => <TableHead key={c.field}>{c.header}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {removedRows.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell className="font-mono">{row.key}</TableCell>
                    {valueColumns.map((c) => <TableCell key={c.field} className="whitespace-normal">{row.values[c.field] ?? ''}</TableCell>)}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {removedPages}
        </TabsContent>
        <TabsContent value="rejected">
          {!report.rejected?.length ? empty : (
            <Table data-testid="import-rejected">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.row')}</TableHead>
                  <TableHead>{t('import.key')}</TableHead>
                  <TableHead>{t('import.message')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rejectedRows.map((row) => (
                  <TableRow key={row.row}>
                    <TableCell>{row.row}</TableCell>
                    <TableCell className="font-mono">{row.key}</TableCell>
                    <TableCell className="whitespace-normal">
                      {row.issues.map((issue, i) => (
                        <span key={`${issue.code}-${i}`} className="block">
                          {issue.header ? `${issue.header}: ` : ''}
                          {issueText(issue)}
                        </span>
                      ))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {rejectedPages}
        </TabsContent>
        <TabsContent value="ar">
          <div className="flex flex-col gap-3" data-testid="import-ar">
            {arRules.map(([code, items]) => (
              <section key={code} data-testid={`import-ar-${code}`}>
                <h4 className="flex items-center gap-2 text-sm font-medium">
                  <Badge variant={items.length ? 'outline' : 'secondary'}>{code}</Badge>
                  {t(`articles.rules.${code}.title`)}
                  <span className="text-muted-foreground" data-testid={`import-ar-count-${code}`}>
                    {new Set(items.map((i) => i.row)).size}
                  </span>
                </h4>
                {items.length ? (
                  <ul className="mt-1 flex flex-col gap-0.5 text-sm">
                    {items.map((i) => (
                      <li key={`${i.row}-${i.field}-${i.problem}`}>
                        {t('import.rowOnly', { row: i.row })} · <span className="font-mono text-xs">{i.key}</span> {i.name} —{' '}
                        {findingText(t, i, fieldNames)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="corrections">
          {!report.corrections?.length ? empty : (
            <Table data-testid="import-corrections">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('import.row')}</TableHead>
                  <TableHead>{t('import.key')}</TableHead>
                  <TableHead>{t('import.message')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {correctionRows.map((c) => (
                  <TableRow key={`${c.row}-${c.field}`}>
                    <TableCell>{c.row}</TableCell>
                    <TableCell className="font-mono">{c.key}</TableCell>
                    <TableCell className="whitespace-normal">{t(`articles.corrections.${c.code}`, { field: c.field, value: c.value })}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {correctionPages}
        </TabsContent>
        <TabsContent value="errors">
          <Issues issues={report.errors} testId="import-errors" />
        </TabsContent>
        <TabsContent value="warnings">
          <Issues issues={report.warnings} testId="import-warnings" />
        </TabsContent>
      </div>
    </Tabs>
  );
}

export function ImportWizard({ open, onOpenChange, title, start, onApplied, fieldNames = {} }: Props): React.JSX.Element {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [progress, setProgress] = useState(0);

  const upload = useMutation({
    mutationFn: start,
    onMutate: () => setProgress(10),
    onSuccess: (job) => setJobId(job.id),
    onError: (error) => setUploadError(describeApiError(error, t).message),
  });
  const job = useQuery({
    queryKey: ['import-jobs', jobId],
    queryFn: () => fetchImportJob(jobId ?? ''),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'analyzing' ? POLL_MS : false),
  });
  const apply = useMutation({
    mutationFn: () => applyImportJob(jobId ?? ''),
    onSuccess: (applied) => {
      job.refetch().catch(() => undefined);
      onApplied?.(applied);
    },
    onError: (error) => notifyError(error, t),
  });

  const current = job.data;
  const analyzing = upload.isPending || (jobId !== null && (!current || current.status === 'analyzing'));
  const blocked = Boolean(current?.counts.errors);
  const reset = () => {
    setFile(null);
    setJobId(null);
    setUploadError(null);
    upload.reset();
    apply.reset();
  };
  const changeOpen = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };
  // The server does not report how far it is: the bar creeps towards 90 %
  // while the analysis runs.
  useEffect(() => {
    if (!analyzing) return undefined;
    const timer = setInterval(() => setProgress((p) => p + (90 - p) * 0.2), POLL_MS / 2);
    return () => clearInterval(timer);
  }, [analyzing]);

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-4xl" data-testid="import-wizard">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{t('import.chooseHint')}</DialogDescription>
        </DialogHeader>

        {jobId === null && !upload.isPending ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="import-file">{t('import.chooseFile')}</Label>
            <Input
              id="import-file"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              data-testid="import-file"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setUploadError(null);
              }}
            />
            {uploadError ? (
              <p className="text-sm text-destructive" role="alert" data-testid="import-upload-error">
                {uploadError}
              </p>
            ) : null}
          </div>
        ) : null}

        {analyzing ? (
          <div className="flex flex-col gap-2" data-testid="import-progress">
            <p className="text-sm text-muted-foreground">{t('import.analyzing')}</p>
            <Progress value={progress} aria-label={t('import.analyzing')} />
          </div>
        ) : null}

        {current?.status === 'failed' ? (
          <Alert variant="destructive" data-testid="import-failed">
            <AlertTitle>{t('import.failed')}</AlertTitle>
            <AlertDescription>
              {t(`errors.${current.error_code ?? 'import_failed'}`, { ...current.error_params, defaultValue: humanize(current.error_code ?? 'import_failed') })}
            </AlertDescription>
          </Alert>
        ) : null}

        {current?.report && current.status !== 'failed' ? (
          <div className="flex flex-col gap-3" data-testid="import-report">
            <p className="text-sm" data-testid="import-summary">
              {t('import.summary', {
                rows: current.counts.rows ?? 0,
                new: current.counts.new ?? 0,
                modified: current.counts.modified ?? 0,
                unchanged: current.counts.unchanged ?? 0,
              })}
              {current.counts.rejected ? ` ${t('import.rejectedSummary', { count: current.counts.rejected })}` : ''}
            </p>
            {blocked ? (
              <Alert variant="destructive" data-testid="import-blocked">
                <AlertDescription>{t('import.blocked')}</AlertDescription>
              </Alert>
            ) : null}
            {current.status === 'applied' ? (
              <Alert data-testid="import-done">
                <AlertTitle>{t('import.done')}</AlertTitle>
                <AlertDescription>{t('import.doneSummary', { new: current.counts.new ?? 0, modified: current.counts.modified ?? 0 })}</AlertDescription>
              </Alert>
            ) : null}
            <Report report={current.report} counts={current.counts} fieldNames={fieldNames} />
          </div>
        ) : null}

        <DialogFooter>
          {jobId === null ? (
            <>
              <Button variant="outline" onClick={() => changeOpen(false)}>
                {t('actions.cancel')}
              </Button>
              <Button disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)} data-testid="import-analyze">
                {t('import.analyze')}
              </Button>
            </>
          ) : current && current.status !== 'analyzing' ? (
            <>
              <Button variant="outline" onClick={reset} data-testid="import-another">
                {t('import.another')}
              </Button>
              {current.status === 'analyzed' ? (
                <Button disabled={blocked || apply.isPending} onClick={() => apply.mutate()} data-testid="import-apply">
                  {apply.isPending ? t('import.applying') : t('import.apply')}
                </Button>
              ) : (
                <Button onClick={() => changeOpen(false)}>{t('actions.close')}</Button>
              )}
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
