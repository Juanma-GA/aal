import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { fetchDiff } from '@/services/catalogApi';
import type { CatalogVersion, DiffChange } from '@/types/catalog';

const ALL = 'all';
const CHANGES: DiffChange[] = ['new', 'modified', 'removed'];

function VersionSelect({ id, label, value, versions, onChange }: {
  id: string;
  label: string;
  value: string;
  versions: CatalogVersion[];
  onChange: (v: string) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full sm:w-72">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {versions.map((v) => (
            <SelectItem key={v.id} value={v.id}>
              {t('catalog.versionLabel', { number: v.number, label: v.label })}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** "Comparar versiones": what changed from one version to another, SNS by SNS. */
export function CompareView({ versions, onOpen }: { versions: CatalogVersion[]; onOpen: (sns: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const [from, setFrom] = useState(versions[1]?.id ?? versions[0]?.id ?? '');
  const [to, setTo] = useState(versions[0]?.id ?? '');
  const [change, setChange] = useState<DiffChange | typeof ALL>(ALL);
  const [page, setPage] = useState(1);
  const diff = useQuery({
    queryKey: ['catalog', 'diff', from, to, change, page],
    queryFn: () => fetchDiff(from, to, change === ALL ? undefined : change, page),
    enabled: Boolean(from && to),
  });
  if (versions.length < 2) return <p className="text-sm text-muted-foreground">{t('catalog.compareNeedsTwo')}</p>;
  const data = diff.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <div className="flex flex-col gap-4" data-testid="catalog-compare">
      <div className="flex flex-wrap items-end gap-4">
        <VersionSelect id="compare-from" label={t('catalog.compareFrom')} value={from} versions={versions} onChange={(v) => { setFrom(v); setPage(1); }} />
        <VersionSelect id="compare-to" label={t('catalog.compareTo')} value={to} versions={versions} onChange={(v) => { setTo(v); setPage(1); }} />
        <div className="flex flex-col gap-1">
          <Label htmlFor="compare-change">{t('catalog.changeKind')}</Label>
          <Select value={change} onValueChange={(v) => { setChange(v as DiffChange | typeof ALL); setPage(1); }}>
            <SelectTrigger id="compare-change" className="w-full sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t('catalog.allChanges')}</SelectItem>
              {CHANGES.map((c) => (
                <SelectItem key={c} value={c}>
                  {t(`catalog.changes.${c}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {!data ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <>
          <div className="flex flex-wrap gap-2" data-testid="compare-summary">
            {[...CHANGES, 'unchanged' as const].map((c) => (
              <Badge key={c} variant="secondary">
                {t(`catalog.changes.${c}`)}: {data.summary[c]}
              </Badge>
            ))}
          </div>
          {data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('catalog.noDifferences')}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('catalog.sns')}</TableHead>
                  <TableHead>{t('catalog.changeKind')}</TableHead>
                  <TableHead>{t('import.field')}</TableHead>
                  <TableHead>{t('import.before')}</TableHead>
                  <TableHead>{t('import.after')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((item) =>
                  (item.changes.length ? item.changes : [null]).map((c, i) => (
                    <TableRow key={`${item.sns}-${c?.field ?? i}`}>
                      <TableCell>
                        {i === 0 ? (
                          <button type="button" className="text-left text-link underline-offset-2 hover:underline" onClick={() => onOpen(item.sns)}>
                            <span className="font-mono text-xs">{item.sns}</span> {item.name}
                          </button>
                        ) : null}
                      </TableCell>
                      <TableCell>{i === 0 ? t(`catalog.changes.${item.change}`) : ''}</TableCell>
                      <TableCell>{c?.header ?? ''}</TableCell>
                      <TableCell className="whitespace-normal text-muted-foreground">{c?.before ?? ''}</TableCell>
                      <TableCell className="whitespace-normal">{c?.after ?? ''}</TableCell>
                    </TableRow>
                  )),
                )}
              </TableBody>
            </Table>
          )}
          {pages > 1 ? (
            <div className="flex items-center justify-end gap-2 text-sm">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t('actions.previous')}
              </Button>
              {t('catalog.page', { page, pages })}
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                {t('actions.next')}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
