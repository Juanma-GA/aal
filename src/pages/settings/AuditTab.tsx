import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { catalogLabel } from '@/lib/labels';
import { fetchAudit, fetchAuditFacets, fetchMaterials, fetchUsers } from '@/services/adminApi';
import type { AuditEntry, AuditFilters } from '@/types/auth';

const ALL = '__all__';

function FilterSelect({
  label,
  value,
  allLabel,
  options,
  onChange,
}: {
  label: string;
  value: string | undefined;
  allLabel: string;
  options: { value: string; label: string }[];
  onChange: (value: string | undefined) => void;
}): React.JSX.Element {
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger className="w-full sm:w-52" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function Json({ value }: { value: unknown }): React.JSX.Element {
  const { t } = useTranslation();
  if (value === null || value === undefined) return <p className="text-sm text-muted-foreground">{t('settings.audit.nothing')}</p>;
  return <pre className="overflow-x-auto rounded-md border bg-muted p-3 font-mono text-xs text-foreground">{JSON.stringify(value, null, 2)}</pre>;
}

/** Date input (yyyy-mm-dd) to the start or end of that day, in UTC. */
const dayBound = (day: string, end: boolean): string | undefined => (day ? `${day}T${end ? '23:59:59.999' : '00:00:00'}Z` : undefined);

export function AuditTab(): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const [filters, setFilters] = useState<AuditFilters>({ page: 1 });
  const [days, setDays] = useState({ from: '', to: '' });
  const [detail, setDetail] = useState<AuditEntry | null>(null);
  const query = { ...filters, date_from: dayBound(days.from, false), date_to: dayBound(days.to, true) };
  const audit = useQuery({ queryKey: ['audit', query], queryFn: () => fetchAudit(query), placeholderData: keepPreviousData });
  const facets = useQuery({ queryKey: ['audit', 'facets'], queryFn: fetchAuditFacets });
  const users = useQuery({ queryKey: ['users'], queryFn: fetchUsers });
  const materials = useQuery({ queryKey: ['materials'], queryFn: fetchMaterials });
  const set = (patch: Partial<AuditFilters>) => setFilters((f) => ({ ...f, ...patch, page: patch.page ?? 1 }));
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(iso));
  // No user: the system itself; a user id without email: a user removed
  // from the database since (the log keeps the row).
  const who = (entry: AuditEntry) => entry.user_email ?? (entry.user_id ? t('settings.audit.removedUser') : t('settings.audit.system'));
  const pages = audit.data ? Math.max(1, Math.ceil(audit.data.total / audit.data.page_size)) : 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-2">
        <FilterSelect
          label={t('settings.audit.who')}
          value={filters.user_id}
          allLabel={t('settings.audit.allUsers')}
          options={(users.data ?? []).map((u) => ({ value: u.id, label: u.email }))}
          onChange={(user_id) => set({ user_id })}
        />
        <FilterSelect
          label={t('settings.audit.material')}
          value={filters.material_id}
          allLabel={t('settings.audit.allMaterials')}
          options={(materials.data ?? []).map((m) => ({ value: m.id, label: m.name }))}
          onChange={(material_id) => set({ material_id })}
        />
        <FilterSelect
          label={t('settings.audit.entity')}
          value={filters.entity_type}
          allLabel={t('settings.audit.allEntities')}
          options={(facets.data?.entity_types ?? []).map((e) => ({ value: e, label: catalogLabel(t, 'audit.entities', e) }))}
          onChange={(entity_type) => set({ entity_type })}
        />
        <FilterSelect
          label={t('settings.audit.action')}
          value={filters.action}
          allLabel={t('settings.audit.allActions')}
          options={(facets.data?.actions ?? []).map((a) => ({ value: a, label: catalogLabel(t, 'audit.actions', a) }))}
          onChange={(action) => set({ action })}
        />
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-from">{t('settings.audit.from')}</Label>
          <Input id="audit-from" type="date" value={days.from} onChange={(e) => (setDays((d) => ({ ...d, from: e.target.value })), set({}))} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-to">{t('settings.audit.to')}</Label>
          <Input id="audit-to" type="date" value={days.to} onChange={(e) => (setDays((d) => ({ ...d, to: e.target.value })), set({}))} />
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            setFilters({ page: 1 });
            setDays({ from: '', to: '' });
          }}
        >
          {t('actions.clearFilters')}
        </Button>
      </div>
      {!audit.data ? (
        <Skeleton className="h-60 w-full" />
      ) : (
        <>
          <Table data-testid="audit-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t('settings.audit.when')}</TableHead>
                <TableHead>{t('settings.audit.who')}</TableHead>
                <TableHead>{t('settings.audit.action')}</TableHead>
                <TableHead>{t('settings.audit.entity')}</TableHead>
                <TableHead>{t('settings.audit.material')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.data.items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    {t('settings.audit.empty')}
                  </TableCell>
                </TableRow>
              ) : (
                audit.data.items.map((entry) => (
                  <TableRow key={entry.id} className="cursor-pointer" onClick={() => setDetail(entry)} data-testid="audit-row">
                    <TableCell className="font-mono text-xs">{when(entry.created_at)}</TableCell>
                    <TableCell>{who(entry)}</TableCell>
                    <TableCell>
                      <Button variant="link" className="h-auto p-0" onClick={() => setDetail(entry)}>
                        {catalogLabel(t, 'audit.actions', entry.action)}
                      </Button>
                    </TableCell>
                    <TableCell>{catalogLabel(t, 'audit.entities', entry.entity_type)}</TableCell>
                    <TableCell>{entry.material_name ?? t('material.empty')}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t('settings.audit.page', { page: audit.data.page, pages, total: audit.data.total })}
            </span>
            <Button className="ml-auto" variant="outline" size="sm" disabled={audit.data.page <= 1} onClick={() => set({ page: audit.data.page - 1 })}>
              {t('actions.previous')}
            </Button>
            <Button variant="outline" size="sm" disabled={audit.data.page >= pages} onClick={() => set({ page: audit.data.page + 1 })}>
              {t('actions.next')}
            </Button>
          </div>
        </>
      )}
      <Sheet open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{detail ? catalogLabel(t, 'audit.actions', detail.action) : t('settings.audit.detailTitle')}</SheetTitle>
            <SheetDescription>
              {detail ? `${when(detail.created_at)} · ${who(detail)}` : null}
            </SheetDescription>
          </SheetHeader>
          {detail ? (
            <div className="flex flex-col gap-4 px-4 pb-6" data-testid="audit-detail">
              {detail.ip ? (
                <p className="text-sm text-muted-foreground">
                  {t('settings.audit.ip')}: <span className="font-mono">{detail.ip}</span>
                </p>
              ) : null}
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-medium text-foreground">{t('settings.audit.before')}</h3>
                <Json value={detail.before} />
              </div>
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-medium text-foreground">{t('settings.audit.after')}</h3>
                <Json value={detail.after} />
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
