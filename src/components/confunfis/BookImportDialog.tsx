// Importing the CONFUNFIS book of a CUF (E15, Anexo XI or Libro AAL): the
// E03 two phases (upload, server analysis polled from Postgres, apply) with
// what a whole book needs: the mode, the confirmation of a file whose CUF
// is another, the report per sheet and per change type, and what the result
// would have (observations, provisional articles, new P/N, shared parts).
import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChangeValue, FullScreenToggle, ImportFailure } from '@/components/import/ChangeDetail';
import { AFTER_CELL, BEFORE_CELL, useDialogSize } from '@/components/import/dialogSize';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { findingTitle } from '@/lib/confunfisText';
import { humanize } from '@/lib/humanize';
import { notifyError } from '@/lib/notify';
import { cn } from '@/lib/utils';
import { describeApiError } from '@/services/apiErrors';
import { applyBookImport, fetchBookJob, startBookImport } from '@/services/confunfisBookApi';
import { BOOK_CHANGES, BOOK_SHEETS, type BookChange, type BookItem, type BookJob, type BookMode, type BookReport, type BookSheet } from '@/types/confunfisBook';
import type { ImportIssue } from '@/types/imports';

const POLL_MS = 1000;
const PAGE_SIZE = 200;
const MODES: BookMode[] = ['merge', 'replace'];

interface Props {
  materialId: string;
  materialName: string;
  /** Which book the user said it is: only the title (the server reads both alike). */
  book: 'anexo' | 'aal';
  /** Only the admin may replace (the server refuses it to anyone else). */
  isAdmin: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplied: () => void;
}

function useIssueText() {
  const { t } = useTranslation();
  // The book's rows go through the CONFUNFIS services: their problems have their texts there (E13/E14).
  return (issue: ImportIssue) =>
    t([`import.issues.${issue.code}`, `confunfis.problems.${issue.code}`], { ...issue.params, defaultValue: '' }) || humanize(issue.code);
}

function Items({ change, items }: { change: BookChange; items: BookItem[] }): React.JSX.Element {
  const { t } = useTranslation();
  const issueText = useIssueText();
  const [page, setPage] = useState(0);
  if (items.length === 0) return <p className="py-4 text-sm text-muted-foreground">{t('import.nothing')}</p>;
  const pages = Math.ceil(items.length / PAGE_SIZE);
  const shown = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  return (
    <>
      <Table data-testid={`book-items-${change}`}>
        <TableHeader>
          <TableRow>
            <TableHead>{t('import.row')}</TableHead>
            <TableHead>{t('import.key')}</TableHead>
            {change === 'rejected' ? null : <TableHead>{t('confunfisBook.name')}</TableHead>}
            <TableHead>{change === 'modified' ? t('import.field') : change === 'rejected' ? t('confunfisBook.detail') : null}</TableHead>
            {change === 'modified' ? (
              <>
                <TableHead>{t('import.before')}</TableHead>
                <TableHead>{t('import.after')}</TableHead>
              </>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.flatMap((item, n) => {
            const rowCell =
              item.row ?? (item.with_row ? t('confunfisBook.withRow') : item.not_in_file || change === 'removed' ? t('confunfisBook.notInFile') : '');
            if (change === 'modified') {
              return (item.changes ?? []).map((c, i) => (
                <TableRow key={`${n}-${c.field}`}>
                  <TableCell>{i === 0 ? rowCell : ''}</TableCell>
                  <TableCell className="font-mono">{i === 0 ? item.key : ''}</TableCell>
                  <TableCell className="whitespace-normal">{i === 0 ? (item.values?.name ?? '') : ''}</TableCell>
                  <TableCell>{c.header}</TableCell>
                  <TableCell className={BEFORE_CELL}><ChangeValue change={c} side="before" /></TableCell>
                  <TableCell className={AFTER_CELL}><ChangeValue change={c} side="after" /></TableCell>
                </TableRow>
              ));
            }
            return [
              <TableRow key={n}>
                <TableCell className="whitespace-nowrap">{rowCell}</TableCell>
                <TableCell className="font-mono">{item.key}</TableCell>
                <TableCell className="whitespace-normal">
                  {change === 'rejected'
                    ? (item.issues ?? []).map((issue, i) => (
                        <span key={`${issue.code}-${i}`} className="block">{issue.header ? `${issue.header}: ` : ''}{issueText(issue)}</span>
                      ))
                    : (item.values?.name ?? '')}
                </TableCell>
                {change === 'rejected' ? null : <TableCell />}
              </TableRow>,
            ];
          })}
        </TableBody>
      </Table>
      {pages > 1 ? (
        <div className="flex items-center justify-end gap-2 py-2 text-sm">
          <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>{t('actions.previous')}</Button>
          {t('import.page', { page: page + 1, pages, total: items.length })}
          <Button size="sm" variant="outline" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>{t('actions.next')}</Button>
        </div>
      ) : null}
    </>
  );
}

function SheetReport({ name, sheet }: { name: string; sheet: BookSheet }): React.JSX.Element {
  const { t } = useTranslation();
  // What the key column means on this sheet ("SNS CO AL ← conjunto superior").
  const legend = t(`confunfisBook.keyLegend.${name}`);
  const [change, setChange] = useState<BookChange>(
    sheet.rejected.length ? 'rejected' : sheet.modified.length ? 'modified' : sheet.new.length ? 'new' : sheet.removed.length ? 'removed' : 'unchanged',
  );
  return (
    <Tabs value={change} onValueChange={(v) => setChange(v as BookChange)}>
      <p className="text-xs text-muted-foreground" data-testid={`book-key-legend-${name}`}>{legend}</p>
      <TabsList className="flex-wrap">
        {BOOK_CHANGES.map((c) => (
          <TabsTrigger key={c} value={c} data-testid={`book-change-${c}`}>
            {t(`import.tabs.${c}`)}
            <Badge variant={c === 'rejected' && sheet.rejected.length ? 'destructive' : 'secondary'} data-testid={`book-count-${name}-${c}`}>{sheet[c].length}</Badge>
          </TabsTrigger>
        ))}
      </TabsList>
      {BOOK_CHANGES.map((c) => (
        <TabsContent key={c} value={c}>
          <Items change={c} items={sheet[c]} />
        </TabsContent>
      ))}
    </Tabs>
  );
}

function ResultReport({ result }: { result: NonNullable<BookReport['result']> }): React.JSX.Element {
  const { t } = useTranslation();
  const observations = Object.entries(result.observations);
  const section = (title: string, testId: string, count: number, body: React.ReactNode) => (
    <section data-testid={testId} className="flex flex-col gap-1">
      <h4 className="flex items-center gap-2 text-sm font-medium">{title}<Badge variant="secondary">{count}</Badge></h4>
      {count ? body : <p className="text-sm text-muted-foreground">{t('import.nothing')}</p>}
    </section>
  );
  return (
    <div className="flex flex-col gap-4 py-2 text-sm">
      {section(t('confunfisBook.result.observations'), 'book-result-observations', observations.length, (
        <ul className="flex flex-col gap-0.5">
          {observations.map(([code, n]) => (
            <li key={code}><Badge variant="outline" className="mr-2">{code}</Badge>{findingTitle(t, code)} · {t('confunfisBook.result.times', { count: n })}</li>
          ))}
        </ul>
      ))}
      {section(t('confunfisBook.result.provisional'), 'book-result-provisional', result.provisional_articles.length, (
        <ul className="flex flex-col gap-0.5">
          {result.provisional_articles.map((a, i) => <li key={`${a.name}-${i}`}>{a.noc ? <span className="mr-2 font-mono">{a.noc}</span> : null}{a.name}</li>)}
        </ul>
      ))}
      {section(t('confunfisBook.result.references'), 'book-result-references', result.new_references.length, (
        <ul className="flex flex-col gap-0.5">
          {result.new_references.map((r, i) => <li key={`${r.pn}-${r.ncage ?? ''}-${i}`}><span className="font-mono">{r.pn}{r.ncage ? ` / ${r.ncage}` : ''}</span> → {r.article}</li>)}
        </ul>
      ))}
      {section(t('confunfisBook.result.globalParts'), 'book-result-global-parts', result.global_parts.length, (
        <>
          <p className="text-muted-foreground">{t('confunfisBook.result.globalPartsHint')}</p>
          <ul className="flex flex-col gap-0.5">
            {result.global_parts.map((p) => (
              <li key={`${p.article}-${p.noc ?? ''}`}>
                {p.article}: {[...p.materials, ...(p.others ? [t('confunfisBook.result.others', { count: p.others })] : [])].join(', ')}
              </li>
            ))}
          </ul>
        </>
      ))}
    </div>
  );
}

function Report({ report, scroll }: { report: BookReport; scroll: string }): React.JSX.Element {
  const { t } = useTranslation();
  const sheets = BOOK_SHEETS.filter((s) => report.sheets[s]);
  const [tab, setTab] = useState<string>(sheets[0] ?? 'result');
  const changes = (s: BookSheet) => s.new.length + s.modified.length + s.removed.length + s.rejected.length;
  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList className="flex-wrap">
        {sheets.map((s) => {
          const sheet = report.sheets[s] as BookSheet;
          return (
            <TabsTrigger key={s} value={s} data-testid={`book-sheet-${s}`}>
              {t(`confunfisBook.sheets.${s}`)}
              <Badge variant={sheet.rejected.length ? 'destructive' : 'secondary'}>{changes(sheet)}</Badge>
            </TabsTrigger>
          );
        })}
        {report.result ? <TabsTrigger value="result" data-testid="book-sheet-result">{t('confunfisBook.result.title')}</TabsTrigger> : null}
      </TabsList>
      <div className={scroll}>
        {sheets.map((s) => (
          <TabsContent key={s} value={s}>
            <SheetReport name={s} sheet={report.sheets[s] as BookSheet} />
          </TabsContent>
        ))}
        {report.result ? (
          <TabsContent value="result">
            <ResultReport result={report.result} />
          </TabsContent>
        ) : null}
      </div>
    </Tabs>
  );
}

export function BookImportDialog({ materialId, materialName, book, isAdmin, open, onOpenChange, onApplied }: Props): React.JSX.Element {
  const { t } = useTranslation();
  const issueText = useIssueText();
  const [mode, setMode] = useState<BookMode>('merge');
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [confirmCuf, setConfirmCuf] = useState(false);
  const [typedName, setTypedName] = useState('');
  const [progress, setProgress] = useState(0);

  const upload = useMutation({
    mutationFn: (f: File) => startBookImport(materialId, mode, f),
    onMutate: () => setProgress(10),
    onSuccess: (job) => setJobId(job.id),
    onError: (error) => setUploadError(describeApiError(error, t).message),
  });
  const job = useQuery({
    queryKey: ['import-jobs', jobId],
    queryFn: () => fetchBookJob(jobId ?? ''),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'analyzing' ? POLL_MS : false),
  });
  const apply = useMutation({
    mutationFn: () => applyBookImport(materialId, jobId ?? '', { confirm_cuf: confirmCuf, confirm_name: mode === 'replace' ? typedName.trim() : null }),
    onSuccess: () => {
      job.refetch().catch(() => undefined);
      onApplied();
    },
    onError: (error) => notifyError(error, t),
  });

  const current: BookJob | undefined = job.data;
  const report = current?.report ?? null;
  const analyzing = upload.isPending || (jobId !== null && (!current || current.status === 'analyzing'));
  const errors = report?.errors ?? [];
  const cufDiffers = Boolean(report?.cuf?.differs);
  const nameOk = mode !== 'replace' || typedName.trim() === materialName;
  const replaceRejected = mode === 'replace' && Boolean(current?.counts.rejected);
  const canApply = current?.status === 'analyzed' && errors.length === 0 && !replaceRejected && (!cufDiffers || confirmCuf) && nameOk && !apply.isPending;
  const reset = () => {
    setFile(null);
    setJobId(null);
    setUploadError(null);
    setConfirmCuf(false);
    setTypedName('');
    upload.reset();
    apply.reset();
  };
  const changeOpen = (next: boolean) => {
    if (!next) {
      reset();
      setMode('merge');
    }
    onOpenChange(next);
  };
  useEffect(() => {
    if (!analyzing) return undefined;
    const timer = setInterval(() => setProgress((p) => p + (90 - p) * 0.2), POLL_MS / 2);
    return () => clearInterval(timer);
  }, [analyzing]);
  const counts = current?.counts ?? {};
  const size = useDialogSize((counts.new ?? 0) + (counts.modified ?? 0) + (counts.removed ?? 0));

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className={size.content} data-testid="book-import">
        <DialogHeader>
          <DialogTitle>{t(`confunfisBook.importTitle.${book}`, { name: materialName })}</DialogTitle>
          <DialogDescription>{t('confunfisBook.importHint')}</DialogDescription>
        </DialogHeader>

        {jobId === null && !upload.isPending ? (
          <div className="flex flex-col gap-3">
            <div role="radiogroup" aria-label={t('confunfisBook.mode')} className="grid gap-2 sm:grid-cols-2">
              {MODES.map((m) => {
                const disabled = m === 'replace' && !isAdmin;
                return (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={mode === m}
                    disabled={disabled}
                    onClick={() => setMode(m)}
                    data-testid={`book-mode-${m}`}
                    className={cn(
                      'flex flex-col gap-1 rounded-md border p-3 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      mode === m ? 'border-primary bg-accent' : 'hover:bg-accent',
                    )}
                  >
                    <span className="font-medium">{t(`confunfisBook.modes.${m}.title`)}</span>
                    <span className="text-muted-foreground">{t(`confunfisBook.modes.${m}.text`)}</span>
                    {disabled ? <span className="text-xs text-muted-foreground">{t('confunfisBook.modes.replace.adminOnly')}</span> : null}
                  </button>
                );
              })}
            </div>
            <Label htmlFor="book-file">{t('import.chooseFile')}</Label>
            <Input
              id="book-file"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              data-testid="book-file"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setUploadError(null);
              }}
            />
            {uploadError ? <p className="text-sm text-destructive" role="alert" data-testid="book-upload-error">{uploadError}</p> : null}
          </div>
        ) : null}

        {analyzing ? (
          <div className="flex flex-col gap-2" data-testid="book-progress">
            <p className="text-sm text-muted-foreground">{t('import.analyzing')}</p>
            <Progress value={progress} aria-label={t('import.analyzing')} />
          </div>
        ) : null}

        {current?.status === 'failed' ? (
          <ImportFailure code={current.error_code} params={current.error_params} testId="book-failed" />
        ) : null}

        {report && current?.status !== 'failed' ? (
          <div className="flex flex-col gap-3" data-testid="book-report">
            <p className="text-sm" data-testid="book-summary">
              {t(`confunfisBook.modes.${report.mode}.title`)} ·{' '}
              {t('confunfisBook.summary', {
                new: counts.new ?? 0, modified: counts.modified ?? 0, unchanged: counts.unchanged ?? 0, removed: counts.removed ?? 0, rejected: counts.rejected ?? 0,
              })}
            </p>
            {errors.length ? (
              <Alert variant="destructive" data-testid="book-errors">
                <AlertTitle>{t('import.blocked')}</AlertTitle>
                <AlertDescription>
                  <ul className="flex flex-col gap-0.5">
                    {errors.map((e, i) => (
                      <li key={`${e.code}-${i}`}>
                        {e.sheet ? `${e.sheet} · ` : ''}
                        {e.row ? `${t('import.rowOnly', { row: e.row })} · ` : ''}
                        {e.header ? `${e.header}: ` : ''}
                        {issueText(e)}
                      </li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}
            {report.notices.some((n) => n.code === 'no_subcategories') ? (
              <Alert className="border-warning" data-testid="book-no-subcategories">
                <AlertDescription>{t('confunfisBook.noSubcategories')}</AlertDescription>
              </Alert>
            ) : null}
            {report.ignored_sheets.length ? (
              <Alert data-testid="book-ignored">
                <AlertDescription>{t('confunfisBook.ignored', { sheets: report.ignored_sheets.join(', ') })}</AlertDescription>
              </Alert>
            ) : null}
            {cufDiffers && report.cuf ? (
              <Alert className="border-warning" data-testid="book-cuf-differs">
                <AlertTitle>{t('confunfisBook.cufDiffers.title')}</AlertTitle>
                <AlertDescription className="flex flex-col gap-2">
                  <span>
                    {t('confunfisBook.cufDiffers.text', {
                      file: [...report.cuf.file.noc, ...report.cuf.file.pn].filter(Boolean).join(' / ') || t('reference.none'),
                      material: [report.cuf.material.noc, report.cuf.material.pn].filter(Boolean).join(' / ') || t('reference.none'),
                      name: report.cuf.material.name,
                    })}
                  </span>
                  {current?.status === 'analyzed' ? (
                    <span className="flex items-center gap-2">
                      <Checkbox id="book-confirm-cuf" checked={confirmCuf} onCheckedChange={(c) => setConfirmCuf(c === true)} data-testid="book-confirm-cuf" />
                      <Label htmlFor="book-confirm-cuf">{t('confunfisBook.cufDiffers.confirm', { name: materialName })}</Label>
                    </span>
                  ) : null}
                </AlertDescription>
              </Alert>
            ) : null}
            {current?.status === 'applied' ? (
              <Alert data-testid="book-done">
                <AlertTitle>{t('import.done')}</AlertTitle>
                <AlertDescription>
                  {t('confunfisBook.doneSummary', { new: counts.new ?? 0, modified: counts.modified ?? 0, removed: counts.removed ?? 0 })}
                </AlertDescription>
              </Alert>
            ) : null}
            {errors.length === 0 ? <><FullScreenToggle full={size.full} onToggle={size.toggle} /><Report report={report} scroll={size.scroll} /></> : null}
            {replaceRejected && current?.status === 'analyzed' ? (
              <Alert variant="destructive" data-testid="book-replace-rejected">
                <AlertDescription>{t('confunfisBook.replaceRejected')}</AlertDescription>
              </Alert>
            ) : null}
            {report.mode === 'replace' && current?.status === 'analyzed' && errors.length === 0 && !replaceRejected ? (
              <div className="flex flex-col gap-1">
                <Label htmlFor="book-confirm-name">{t('confunfisBook.replaceConfirm', { name: materialName, count: counts.removed ?? 0 })}</Label>
                <Input id="book-confirm-name" value={typedName} onChange={(e) => setTypedName(e.target.value)} autoComplete="off" data-testid="book-confirm-name" />
              </div>
            ) : null}
          </div>
        ) : null}

        <DialogFooter>
          {jobId === null ? (
            <>
              <Button variant="outline" onClick={() => changeOpen(false)}>{t('actions.cancel')}</Button>
              <Button disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)} data-testid="book-analyze">{t('import.analyze')}</Button>
            </>
          ) : current && current.status !== 'analyzing' ? (
            <>
              <Button variant="outline" onClick={reset} data-testid="book-another">{t('import.another')}</Button>
              {current.status === 'analyzed' ? (
                <Button
                  variant={mode === 'replace' ? 'destructive' : 'default'}
                  disabled={!canApply}
                  onClick={() => apply.mutate()}
                  data-testid="book-apply"
                >
                  {apply.isPending ? t('import.applying') : t('import.apply')}
                </Button>
              ) : (
                <Button onClick={() => changeOpen(false)} data-testid="book-close">{t('actions.close')}</Button>
              )}
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
