import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PAGE_SIZE, useConfunfisRows } from '@/hooks/useConfunfis';
import { findingTitle } from '@/lib/confunfisText';
import { OBSERVATION_CODES, csOf, type ObservationCode, type PositionRow, type RowFilters } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';

const ALL = '__all__';
const ANY = '__any__';
const DEBOUNCE_MS = 300;

/** The CONFUNFIS as the Anexo XI's columns (E13): a search (SNS, NOC, P/N,
 *  name, function), filters (observations, CT SIGLE, orphans, CUF montado)
 *  and the observation badges; a row opens its card. */
export function RowsTable({ materialId, onSelect }: { materialId: string; onSelect: (row: PositionRow) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const [observation, setObservation] = useState(ALL);
  const [ct, setCt] = useState(ALL);
  const [orphans, setOrphans] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => { setQ(text.trim()); setPage(1); }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const filters: RowFilters = {
    q: q || undefined,
    with_observations: observation === ANY ? true : undefined,
    observation: observation !== ALL && observation !== ANY ? (observation as ObservationCode) : undefined,
    ct_sigle: ct === 'S' || ct === 'N' ? ct : undefined,
    orphans: orphans || undefined,
    mounted: mounted || undefined,
  };
  const rows = useConfunfisRows(materialId, filters, page);
  const pages = rows.data ? Math.max(1, Math.ceil(rows.data.total / PAGE_SIZE)) : 1;
  const reset = (fn: () => void) => { fn(); setPage(1); };

  return (
    <div className="flex flex-col gap-3" data-testid="confunfis-table">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-64 flex-1 flex-col gap-1">
          <Label htmlFor="confunfis-search">{t('confunfis.table.search')}</Label>
          <Input id="confunfis-search" type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('confunfis.table.searchHint')} data-testid="confunfis-search" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="confunfis-observation">{t('confunfis.table.observations')}</Label>
          <Select value={observation} onValueChange={(v) => reset(() => setObservation(v))}>
            <SelectTrigger id="confunfis-observation" className="w-64" data-testid="confunfis-filter-observation">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t('confunfis.table.all')}</SelectItem>
              <SelectItem value={ANY}>{t('confunfis.table.withObservations')}</SelectItem>
              {OBSERVATION_CODES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c} · {findingTitle(t, c)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="confunfis-ct">{t('confunfis.fields.ct_sigle')}</Label>
          <Select value={ct} onValueChange={(v) => reset(() => setCt(v))}>
            <SelectTrigger id="confunfis-ct" className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t('confunfis.table.all')}</SelectItem>
              <SelectItem value="S">{t('confunfis.yes')}</SelectItem>
              <SelectItem value="N">{t('confunfis.no')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 pb-2">
          <Checkbox id="confunfis-orphans" checked={orphans} onCheckedChange={(c) => reset(() => setOrphans(c === true))} />
          <Label htmlFor="confunfis-orphans">{t('confunfis.table.orphans')}</Label>
        </div>
        <div className="flex items-center gap-2 pb-2">
          <Checkbox id="confunfis-mounted" checked={mounted} onCheckedChange={(c) => reset(() => setMounted(c === true))} />
          <Label htmlFor="confunfis-mounted">{t('confunfis.table.mounted')}</Label>
        </div>
      </div>
      <p className="text-sm text-muted-foreground" data-testid="confunfis-table-total">{t('confunfis.table.total', { count: rows.data?.total ?? 0 })}</p>
      {!rows.data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="overflow-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('confunfis.fields.sns')}</TableHead>
                <TableHead>{t('confunfis.fields.co')}</TableHead>
                <TableHead>{t('confunfis.fields.al')}</TableHead>
                <TableHead className="text-right">{t('confunfis.fields.qty')}</TableHead>
                <TableHead>{t('confunfis.fields.noc')}</TableHead>
                <TableHead>{t('confunfis.fields.pn')}</TableHead>
                <TableHead>{t('confunfis.fields.ncage')}</TableHead>
                <TableHead>{t('confunfis.fields.article_name')}</TableHead>
                <TableHead>{t('confunfis.fields.ct_sigle')}</TableHead>
                <TableHead>{t('confunfis.fields.cs')}</TableHead>
                <TableHead className="text-right">{t('confunfis.fields.total')}</TableHead>
                <TableHead>{t('confunfis.table.observations')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.data.items.map((r) => (
                <TableRow key={r.id} className="cursor-pointer" onClick={() => onSelect(r)} data-testid={`confunfis-row-${r.sns}-${r.co}-${r.al}`}>
                  <TableCell className="font-mono text-xs">{r.sns}</TableCell>
                  <TableCell className="font-mono text-xs">{r.co}</TableCell>
                  <TableCell className="font-mono text-xs">{r.al}</TableCell>
                  <TableCell className="text-right">{r.qty ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{r.article?.noc ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{r.article?.pn ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{r.article?.ncage ?? '—'}</TableCell>
                  <TableCell className="whitespace-normal">{r.article_name ?? '—'}</TableCell>
                  <TableCell>{r.ct_sigle ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{csOf(r) ?? t('confunfis.theCuf')}</TableCell>
                  <TableCell className="text-right">{r.total ?? '—'}</TableCell>
                  <TableCell>
                    <ObservationBadges row={r} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {pages > 1 ? (
        <div className="flex items-center gap-2 self-end">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('confunfis.table.previous')}</Button>
          <span className="text-sm">{t('confunfis.table.page', { page, pages })}</span>
          <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t('confunfis.table.next')}</Button>
        </div>
      ) : null}
    </div>
  );
}
