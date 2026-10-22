// The two phases of an Excel import (E03), for any template: upload the
// file, wait while the server analyses it (polling the job, Postgres is the
// only record of where it stands: HR1), review the report and apply it.
// E10 (CONF_FUN), E12 (Fichero Carga) and E15 (Anexo XI) use it as it is,
// with their own `start`.
import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { humanize } from '@/lib/humanize';
import { notifyError } from '@/lib/notify';
import { describeApiError } from '@/services/apiErrors';
import { applyImportJob, fetchImportJob } from '@/services/importsApi';
import type { ImportIssue, ImportJob, ImportReport } from '@/types/imports';

const POLL_MS = 1000;
const TABS = ['new', 'modified', 'unchanged', 'errors', 'warnings'] as const;
type Tab = (typeof TABS)[number];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Phase 1: uploads the file and returns the job being analysed. */
  start: (file: File) => Promise<ImportJob>;
  /** After applying: refresh what the import changed. */
  onApplied?: (job: ImportJob) => void;
}

function useIssueText() {
  const { t } = useTranslation();
  return (issue: ImportIssue) => t(`import.issues.${issue.code}`, { ...issue.params, defaultValue: '' }) || humanize(issue.code);
}

function Issues({ issues, testId }: { issues: ImportIssue[]; testId: string }): React.JSX.Element {
  const { t } = useTranslation();
  const text = useIssueText();
  if (issues.length === 0) return <p className="py-4 text-sm text-muted-foreground">{t('import.nothing')}</p>;
  return (
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{t('import.where')}</TableHead>
          <TableHead>{t('import.field')}</TableHead>
          <TableHead>{t('import.message')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {issues.map((issue, i) => (
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
  );
}

function Report({ report, counts }: { report: ImportReport; counts: ImportJob['counts'] }): React.JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>(counts.errors ? 'errors' : counts.modified ? 'modified' : counts.new ? 'new' : 'unchanged');
  const valueColumns = report.columns.filter((c) => c.field !== report.columns[0]?.field);
  const empty = <p className="py-4 text-sm text-muted-foreground">{t('import.nothing')}</p>;
  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
      <TabsList className="flex-wrap">
        {TABS.map((name) => (
          <TabsTrigger key={name} value={name} data-testid={`import-tab-${name}`}>
            {t(`import.tabs.${name}`)}
            <Badge variant={name === 'errors' && counts.errors ? 'destructive' : 'secondary'} data-testid={`import-count-${name}`}>
              {counts[name] ?? 0}
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
                {report.new.map((row) => (
                  <TableRow key={row.row}>
                    <TableCell>{row.row}</TableCell>
                    <TableCell className="font-mono">{row.key}</TableCell>
                    {valueColumns.map((c) => <TableCell key={c.field} className="whitespace-normal">{row.values[c.field] ?? ''}</TableCell>)}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
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
                {report.modified.flatMap((row) =>
                  row.changes.map((change, i) => (
                    <TableRow key={`${row.row}-${change.field}`}>
                      <TableCell>{i === 0 ? row.row : ''}</TableCell>
                      <TableCell className="font-mono">{i === 0 ? row.key : ''}</TableCell>
                      <TableCell>{change.header}</TableCell>
                      <TableCell className="whitespace-normal text-muted-foreground line-through">{change.before}</TableCell>
                      <TableCell className="whitespace-normal">{change.after}</TableCell>
                    </TableRow>
                  )),
                )}
              </TableBody>
            </Table>
          )}
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
                {report.unchanged.map((row) => (
                  <TableRow key={row.row}>
                    <TableCell>{row.row}</TableCell>
                    <TableCell className="font-mono">{row.key}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
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

export function ImportWizard({ open, onOpenChange, title, start, onApplied }: Props): React.JSX.Element {
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
            <Report report={current.report} counts={current.counts} />
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
