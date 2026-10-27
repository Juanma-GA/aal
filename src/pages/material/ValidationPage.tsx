// Validación NT 10/17 (E16, RF-03): the latest validation of the CUF -- its
// traffic light, the summary by rule (pressing one filters), the findings
// with their filters and search, "Ir a" the row (or the article, the
// product), accepting a warning with a justification, and the report as
// PDF or Excel. Reading it needs validacion.ver; validating, validacion.ejecutar;
// accepting, confunfis.editar.
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { TrafficLight } from '@/components/validation/TrafficLight';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { useAcceptFinding, useFindingMessage, useRunValidation, useValidation } from '@/hooks/useValidation';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { findingTarget } from '@/lib/validation';
import { exportValidationReport } from '@/services/validationApi';
import type { Finding } from '@/types/validation';

const ALL = '__all__';

function AcceptDialog({ finding, message, onClose, onAccept }: { finding: Finding; message: string; onClose: () => void; onAccept: (text: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent data-testid="accept-dialog">
        <DialogHeader>
          <DialogTitle>{t('validation.page.acceptTitle', { code: finding.rule_code })}</DialogTitle>
          <DialogDescription>{finding.location} · {message}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1">
          <Label htmlFor="accept-justification">{t('validation.page.justification')}</Label>
          <Input id="accept-justification" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} data-testid="accept-justification" />
          <p className="text-xs text-muted-foreground">{t('validation.page.justificationHint')}</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button disabled={!text.trim()} onClick={() => onAccept(text.trim())} data-testid="accept-save">{t('validation.page.accept')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ValidationPage(): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const material = useMaterialOfPage();
  const navigate = useNavigate();
  const validation = useValidation(material.id);
  const run = useRunValidation(material.id);
  const accept = useAcceptFinding(material.id);
  const message = useFindingMessage();
  const canAccept = material.permissions.includes('confunfis.editar');
  // E17 fleco 1: the observer reads the report but does not run it.
  const canRun = material.permissions.includes('validacion.ejecutar');
  const [rule, setRule] = useState(ALL);
  const [severity, setSeverity] = useState(ALL);
  const [scope, setScope] = useState(ALL);
  const [accepted, setAccepted] = useState(ALL);
  const [text, setText] = useState('');
  const [accepting, setAccepting] = useState<Finding | null>(null);
  const title = t('validation.page.title');
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  const data = validation.data;

  const findings = useMemo(() => {
    const needle = text.trim().toLocaleLowerCase();
    return (data?.findings ?? []).filter(
      (f) =>
        (rule === ALL || f.rule_code === rule) && (severity === ALL || f.severity === severity) && (scope === ALL || f.scope === scope)
        && (accepted === ALL || f.accepted === (accepted === 'yes'))
        && (!needle || `${f.rule_code} ${f.location} ${f.found ?? ''} ${message(f)}`.toLocaleLowerCase().includes(needle)),
    );
    // message depends on the field names only, read with the findings.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, rule, severity, scope, accepted, text]);
  const scopes = [...new Set((data?.findings ?? []).map((f) => f.scope))].sort();

  const download = (format: 'pdf' | 'xlsx') => {
    exportValidationReport(material.id, format)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? `VALIDACION.${format}`))
      .catch((error: unknown) => notifyError(error, t));
  };

  return (
    <div className="flex flex-col gap-6" data-testid="validation-page">
      <PageHeader crumbs={[{ label: material.name, to: `/materiales/${material.id}` }, { label: title }]} title={title} />
      <p className="text-sm text-muted-foreground">{t('validation.page.hint')}</p>
      {!data ? (
        <Skeleton className="h-32 w-full" />
      ) : (
        <>
          <Card>
            <CardContent className="flex flex-col gap-4 pt-6">
              <div className="flex flex-wrap items-center gap-4">
                <TrafficLight validation={data} />
                <div className="flex flex-wrap gap-2 sm:ml-auto">
                  {canRun ? (
                    <Button onClick={() => run.mutate()} disabled={run.isPending} data-testid="validation-run">
                      {run.isPending ? t('validation.page.running') : t('validation.page.run')}
                    </Button>
                  ) : null}
                  <Button variant="outline" disabled={data.state === 'none'} onClick={() => download('pdf')} data-testid="validation-export-pdf">{t('validation.page.exportPdf')}</Button>
                  <Button variant="outline" disabled={data.state === 'none'} onClick={() => download('xlsx')} data-testid="validation-export-xlsx">{t('validation.page.exportXlsx')}</Button>
                </div>
              </div>
              {data.at ? (
                <p className="text-sm text-muted-foreground" data-testid="validation-when">
                  {t('validation.page.when', { at: when(data.at), by: data.by ?? t('validation.page.system'), trigger: t(`validation.page.trigger.${data.trigger ?? 'manual'}`) })}
                  {data.outdated ? ` · ${t(data.outdated_rules ? 'validation.page.outdatedRules' : 'validation.page.outdatedData')}` : ''}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">{t('validation.page.never')}</p>
              )}
              {data.delivery_problems.length ? (
                <Alert data-testid="validation-delivery">
                  <AlertTitle>{t('validation.page.deliveryBlocked')}</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4">
                      {data.delivery_problems.map((p) => <li key={p.code}>{t(`validation.delivery.${p.code}`, p.params)}</li>)}
                    </ul>
                  </AlertDescription>
                </Alert>
              ) : data.state !== 'none' ? (
                <Badge className="w-fit bg-success text-success-foreground" data-testid="validation-delivery-ok">{t('validation.page.deliveryReady')}</Badge>
              ) : null}
            </CardContent>
          </Card>

          {data.by_rule.length ? (
            <Card>
              <CardHeader>
                <CardTitle>{t('validation.page.byRule')}</CardTitle>
                <CardDescription>{t('validation.page.byRuleHint')}</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('validation.page.code')}</TableHead>
                      <TableHead>{t('validation.page.ruleText')}</TableHead>
                      <TableHead>{t('validation.report.ref')}</TableHead>
                      <TableHead>{t('validation.report.severity')}</TableHead>
                      <TableHead className="text-right">{t('validation.report.count')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_rule.map((r) => (
                      <TableRow
                        key={r.code}
                        className={rule === r.code ? 'row-selected cursor-pointer' : 'cursor-pointer hover:bg-accent'}
                        onClick={() => setRule(rule === r.code ? ALL : r.code)}
                        aria-selected={rule === r.code}
                        data-testid={`validation-rule-${r.code}`}
                      >
                        <TableCell className="font-mono">{r.code}</TableCell>
                        <TableCell className="whitespace-normal" title={t(`validation.rules.${r.code}.text`)}>{t(`validation.rules.${r.code}.title`)}</TableCell>
                        <TableCell className="text-muted-foreground">{r.ref}</TableCell>
                        <TableCell><Badge variant={r.severity === 'bloqueante' ? 'destructive' : 'warning'}>{t(`validation.severity.${r.severity}`)}</Badge></TableCell>
                        <TableCell className="text-right tabular-nums">
                          {r.findings}{r.accepted ? ` (${t('validation.page.acceptedShort', { count: r.accepted })})` : ''}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : null}

          {data.state !== 'none' ? (
            <Card>
              <CardHeader>
                <CardTitle>{t('validation.page.findings', { count: findings.length })}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-wrap items-end gap-2">
                  <div className="flex flex-col gap-1">
                    <Label htmlFor="finding-search">{t('validation.page.search')}</Label>
                    <Input id="finding-search" type="search" className="w-full sm:w-64" value={text} onChange={(e) => setText(e.target.value)} data-testid="finding-search" />
                  </div>
                  {[
                    { id: 'rule', value: rule, set: setRule, label: t('validation.report.rule'), options: data.by_rule.map((r) => ({ value: r.code, label: `${r.code} · ${t(`validation.rules.${r.code}.title`)}` })) },
                    { id: 'severity', value: severity, set: setSeverity, label: t('validation.report.severity'), options: (['bloqueante', 'aviso'] as const).map((s) => ({ value: s, label: t(`validation.severity.${s}`) })) },
                    { id: 'scope', value: scope, set: setScope, label: t('validation.page.scope'), options: scopes.map((s) => ({ value: s, label: t(`validation.scope.${s}`) })) },
                    { id: 'accepted', value: accepted, set: setAccepted, label: t('validation.page.acceptedFilter'), options: [{ value: 'yes', label: t('validation.page.onlyAccepted') }, { value: 'no', label: t('validation.page.notAccepted') }] },
                  ].map((filter) => (
                    <div key={filter.id} className="flex flex-col gap-1">
                      <Label htmlFor={`finding-filter-${filter.id}`}>{filter.label}</Label>
                      <Select value={filter.value} onValueChange={filter.set}>
                        <SelectTrigger id={`finding-filter-${filter.id}`} className="w-full sm:w-48" data-testid={`finding-filter-${filter.id}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={ALL}>{t('validation.page.all')}</SelectItem>
                          {filter.options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('validation.page.code')}</TableHead>
                        <TableHead>{t('validation.page.where')}</TableHead>
                        <TableHead>{t('validation.page.what')}</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {findings.map((f) => {
                        const target = findingTarget(material.id, f);
                        return (
                          <TableRow key={f.id} data-testid={`finding-${f.rule_code}`}>
                            <TableCell className="align-top">
                              <span className="flex flex-col gap-1">
                                <Badge variant={f.severity === 'bloqueante' ? 'destructive' : 'warning'} title={t(`validation.severity.${f.severity}`)}>{f.rule_code}</Badge>
                                {f.accepted ? <Badge variant="outline" data-testid="finding-accepted">{t('validation.page.isAccepted')}</Badge> : null}
                              </span>
                            </TableCell>
                            <TableCell className="max-w-72 whitespace-normal align-top font-mono text-xs">{f.location}</TableCell>
                            <TableCell className="min-w-64 whitespace-normal align-top">
                              <p>{message(f)}</p>
                              {f.accepted && f.justification ? (
                                <p className="text-xs text-muted-foreground">{t('validation.page.acceptedBy', { by: f.accepted_by ?? '', at: f.accepted_at ? when(f.accepted_at) : '', text: f.justification })}</p>
                              ) : null}
                            </TableCell>
                            <TableCell className="align-top">
                              <span className="flex justify-end gap-1">
                                {target ? <Button size="sm" variant="outline" onClick={() => navigate(target)} data-testid="finding-goto">{t('validation.page.goTo')}</Button> : null}
                                {canAccept && f.severity === 'aviso' && !f.accepted ? (
                                  <Button size="sm" variant="ghost" onClick={() => setAccepting(f)} data-testid="finding-accept">{t('validation.page.accept')}</Button>
                                ) : null}
                              </span>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
                {!findings.length ? <p className="text-sm text-muted-foreground">{t('validation.page.noFindings')}</p> : null}
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
      {accepting ? (
        <AcceptDialog
          finding={accepting} message={message(accepting)} onClose={() => setAccepting(null)}
          onAccept={(justification) => { accept.mutate({ id: accepting.id, justification }); setAccepting(null); }}
        />
      ) : null}
    </div>
  );
}
