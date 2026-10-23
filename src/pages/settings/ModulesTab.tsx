import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ModuleStatusBadge } from '@/components/modules/ModuleStatus';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { NavRow } from '@/components/layout/NavRow';
import { useActiveMaterial } from '@/hooks/useMaterials';
import { moduleCardHref, modulesKey, useModules } from '@/hooks/useModules';
import { notifyError } from '@/lib/notify';
import { updateModule } from '@/services/modulesApi';
import type { ModuleBrief, ModuleGroup, ModuleStatus } from '@/types/modules';

const ALL = '__all__';
const STATUSES: ModuleStatus[] = ['planificado', 'en_desarrollo', 'disponible'];

interface Editing {
  module: ModuleBrief;
  status: ModuleStatus;
  route: string;
}

function Filter({ label, value, options, onChange, allLabel }: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  allLabel: string;
}): React.JSX.Element {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full sm:w-56" aria-label={label}>
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

/** The module catalog: filter it and change a module's status and route.
 *  The change is confirmed in a dialog, shown at once and saved in the
 *  background; if the server refuses it, it is undone (HR20). The texts
 *  are the seed's and are not edited here. */
export function ModulesTab(): React.JSX.Element {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const modules = useModules();
  const active = useActiveMaterial();
  const [group, setGroup] = useState(ALL);
  const [phase, setPhase] = useState(ALL);
  const [status, setStatus] = useState(ALL);
  const [editing, setEditing] = useState<Editing | null>(null);

  const rows = useMemo(
    () =>
      (modules.data ?? []).flatMap((g) => g.modules.map((m) => ({ group: g, module: m }))).filter(
        ({ group: g, module: m }) => (group === ALL || g.code === group) && (phase === ALL || m.phase === phase) && (status === ALL || m.status === status),
      ),
    [modules.data, group, phase, status],
  );
  const phases = [...new Set((modules.data ?? []).flatMap((g) => g.modules.map((m) => m.phase)))].sort();

  const save = () => {
    if (!editing) return;
    const { module, status: next } = editing;
    const route = next === 'disponible' ? editing.route.trim() : null;
    const previous = queryClient.getQueryData<ModuleGroup[]>(modulesKey);
    const apply = (list: ModuleGroup[], patch: Partial<ModuleBrief>) =>
      list.map((g) => ({ ...g, modules: g.modules.map((m) => (m.code === module.code ? { ...m, ...patch } : m)) }));
    if (previous) queryClient.setQueryData(modulesKey, apply(previous, { status: next, route }));
    setEditing(null);
    updateModule(module.code, module.version, next, route)
      .then((saved) => {
        const current = queryClient.getQueryData<ModuleGroup[]>(modulesKey);
        if (current) queryClient.setQueryData(modulesKey, apply(current, { status: saved.status, route: saved.route, version: saved.version }));
        void queryClient.invalidateQueries({ queryKey: ['modules', module.code] });
      })
      .catch((error: unknown) => {
        if (previous) queryClient.setQueryData(modulesKey, previous);
        notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: modulesKey }));
      });
  };

  if (!modules.data) return <Skeleton className="h-60 w-full" />;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('settings.modules.hint')}</p>
      <div className="flex flex-wrap gap-2">
        <Filter
          label={t('settings.modules.group')}
          value={group}
          onChange={setGroup}
          allLabel={t('settings.modules.allGroups')}
          options={modules.data.map((g) => ({ value: g.code, label: g.name }))}
        />
        <Filter
          label={t('modules.phaseLabel')}
          value={phase}
          onChange={setPhase}
          allLabel={t('settings.modules.allPhases')}
          options={phases.map((p) => ({ value: p, label: t(`modules.phase.${p}`) }))}
        />
        <Filter
          label={t('settings.modules.status')}
          value={status}
          onChange={setStatus}
          allLabel={t('settings.modules.allStatuses')}
          options={STATUSES.map((s) => ({ value: s, label: t(`modules.status.${s}`) }))}
        />
      </div>
      <Table data-testid="modules-table">
        <TableHeader>
          <TableRow>
            <TableHead>{t('settings.modules.module')}</TableHead>
            <TableHead>{t('settings.modules.group')}</TableHead>
            <TableHead>{t('modules.phaseLabel')}</TableHead>
            <TableHead>{t('settings.modules.status')}</TableHead>
            <TableHead>{t('settings.modules.route')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.more')}</span>
            </TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.open')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">
                {t('settings.modules.empty')}
              </TableCell>
            </TableRow>
          ) : (
            rows.map(({ group: g, module: m }) => (
              <NavRow
                key={m.code}
                to={active ? moduleCardHref(m.code, active.id) : undefined}
                label={t('settings.modules.openCard', { name: m.name })}
                data-testid={`module-row-${m.code}`}
              >
                <TableCell className="font-medium whitespace-normal">{m.name}</TableCell>
                <TableCell className="whitespace-normal">{g.name}</TableCell>
                <TableCell>{t(`modules.phase.${m.phase}`)}</TableCell>
                <TableCell>
                  <ModuleStatusBadge status={m.status} />
                </TableCell>
                <TableCell className="font-mono text-xs">{m.route ?? t('material.empty')}</TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" onClick={() => setEditing({ module: m, status: m.status, route: m.route ?? '' })}>
                    {t('settings.modules.change')}
                  </Button>
                </TableCell>
              </NavRow>
            ))
          )}
        </TableBody>
      </Table>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('settings.modules.changeTitle', { name: editing?.module.name ?? '' })}</DialogTitle>
            <DialogDescription>{t('settings.modules.changeHint')}</DialogDescription>
          </DialogHeader>
          {editing ? (
            <div className="flex flex-col gap-4" data-testid="module-form">
              <div className="flex flex-col gap-2">
                <Label htmlFor="module-status">{t('settings.modules.status')}</Label>
                <Select value={editing.status} onValueChange={(v) => setEditing({ ...editing, status: v as ModuleStatus })}>
                  <SelectTrigger id="module-status" className="w-full" data-testid="module-status-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {t(`modules.status.${s}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {editing.status === 'disponible' ? (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="module-route">{t('settings.modules.route')}</Label>
                  <Input
                    id="module-route"
                    className="font-mono"
                    value={editing.route}
                    onChange={(e) => setEditing({ ...editing, route: e.target.value })}
                    aria-describedby="module-route-hint"
                  />
                  <p id="module-route-hint" className="text-xs text-muted-foreground">
                    {t('settings.modules.routeHint')}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={save} disabled={editing?.status === 'disponible' && !editing.route.trim()} data-testid="module-save">
              {t('actions.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
