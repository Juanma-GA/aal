import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { ModuleStatusIcon } from '@/components/modules/ModuleStatus';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCuf } from '@/hooks/useCuf';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { moduleHref, useModules } from '@/hooks/useModules';
import { catalogLabel } from '@/lib/labels';
import { fetchSummary } from '@/services/confunfisApi';
import { fetchActivity, fetchTeam } from '@/services/modulesApi';
import type { ModuleBrief, ModuleStatus } from '@/types/modules';

const FIELDS = ['noc', 'part_number', 'ncage'] as const;
const STATUSES: ModuleStatus[] = ['disponible', 'en_desarrollo', 'planificado'];

function countBy(modules: ModuleBrief[], status: ModuleStatus): number {
  return modules.filter((m) => m.status === status).length;
}

/** The material's Panel: its CUF, the user's role, the team, how far the
 *  AAL modules are, the latest activity and the modules that already work.
 *  All of it real data (no figure is made up). */
export function PanelPage(): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const material = useMaterialOfPage();
  const modules = useModules();
  const cuf = useCuf(material.id);
  const confunfis = useQuery({
    queryKey: ['confunfis', material.id, 'summary'],
    queryFn: () => fetchSummary(material.id),
    enabled: material.permissions.includes('confunfis.ver'),
  });
  const team = useQuery({ queryKey: ['materials', material.id, 'team'], queryFn: () => fetchTeam(material.id) });
  const activity = useQuery({ queryKey: ['materials', material.id, 'activity'], queryFn: () => fetchActivity(material.id) });
  const all = (modules.data ?? []).flatMap((g) => g.modules);
  const phases = [...new Set(all.map((m) => m.phase))].sort();
  const available = all.filter((m) => m.status === 'disponible' && m.code !== 'panel');
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader crumbs={[{ label: material.name }, { label: t('panel.title') }]} title={t('panel.title')} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="active-material">
          <CardHeader>
            <CardDescription>{t('material.activeTitle')}</CardDescription>
            <CardTitle className="text-xl">{material.name}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {material.description ? <p className="text-sm text-foreground">{material.description}</p> : null}
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {FIELDS.map((field) => (
                <div key={field}>
                  <dt className="text-sm text-muted-foreground">{t(`material.fields.${field}`)}</dt>
                  <dd className="font-mono text-sm text-foreground">{material[field] ?? t('material.empty')}</dd>
                </div>
              ))}
            </dl>
            <div className="flex flex-col gap-2">
              <span className="text-sm text-muted-foreground">{t('material.yourRole')}</span>
              <div>
                <Badge variant="secondary" data-testid="panel-role">
                  {material.role ? catalogLabel(t, 'roles', material.role) : t('material.adminRole')}
                </Badge>
              </div>
            </div>
            <div className="flex flex-col gap-2" data-testid="panel-subcategories">
              <span className="text-sm text-muted-foreground">
                {t('cuf.subcategories')} ·{' '}
                <Link to={`/materiales/${material.id}/ficha?tab=configuracion`} className="text-link underline-offset-2 hover:underline" data-testid="panel-sns-count">
                  {cuf.data ? t('cuf.snsCount', { count: cuf.data.sns_count }) : t('material.empty')}
                </Link>
              </span>
              <ul className="flex flex-wrap gap-2">
                {cuf.data?.subcategories.length === 0 ? <li className="text-sm text-muted-foreground">{t('cuf.noSubcategories')}</li> : null}
                {(cuf.data?.subcategories ?? []).map((s) => (
                  <li key={s.code}>
                    <Badge variant="secondary">
                      <span className="font-mono">{s.code}</span> {s.name}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
            {confunfis.data ? (
              <div className="flex flex-col gap-2" data-testid="panel-confunfis">
                <span className="text-sm text-muted-foreground">
                  <Link to={`/materiales/${material.id}/confunfis`} className="text-link underline-offset-2 hover:underline">{t('confunfis.title')}</Link>
                </span>
                <ul className="flex flex-wrap gap-2 text-sm">
                  <li><Badge variant="secondary" data-testid="panel-confunfis-rows">{t('confunfis.summary.rows', { count: confunfis.data.rows })}</Badge></li>
                  <li><Badge variant="secondary">{t('confunfis.summary.positions', { count: confunfis.data.positions })}</Badge></li>
                  <li><Badge variant="secondary">{t('confunfis.summary.covered', { covered: confunfis.data.sns_covered, total: confunfis.data.sns_in_config })}</Badge></li>
                  <li><Badge variant="outline">{t('confunfis.summary.observations', { count: confunfis.data.with_observations })}</Badge></li>
                </ul>
              </div>
            ) : null}
            <div className="flex flex-col gap-2">
              <span className="text-sm text-muted-foreground">{t('material.yourPermissions')}</span>
              <ul className="flex flex-wrap gap-2" data-testid="material-permissions">
                {material.permissions.map((code) => (
                  <li key={code}>
                    <Badge variant="outline">{catalogLabel(t, 'permissions', code)}</Badge>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card data-testid="panel-team">
          <CardHeader>
            <CardTitle>{t('panel.team')}</CardTitle>
            <CardDescription>{t('panel.teamHint')}</CardDescription>
          </CardHeader>
          <CardContent>
            {!team.data ? (
              <Skeleton className="h-20 w-full" />
            ) : team.data.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('panel.noTeam')}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {team.data.map((m) => (
                  <li key={`${m.display_name}-${m.role}`} className="flex items-center justify-between gap-2">
                    <span className="text-sm text-foreground">{m.display_name}</span>
                    <Badge variant="secondary">{catalogLabel(t, 'roles', m.role)}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="panel-progress">
        <CardHeader>
          <CardTitle>{t('panel.progress')}</CardTitle>
          <CardDescription>{t('panel.progressHint')}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {!modules.data ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <>
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {STATUSES.map((status) => (
                  <li key={status} className="flex items-center gap-3 rounded-lg border p-3" data-testid={`panel-count-${status}`}>
                    <ModuleStatusIcon status={status} className="size-5" />
                    <span className="text-2xl font-semibold text-foreground">{countBy(all, status)}</span>
                    <span className="text-sm text-muted-foreground">{t(`modules.status.${status}`)}</span>
                  </li>
                ))}
              </ul>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('modules.phaseLabel')}</TableHead>
                    {STATUSES.map((s) => (
                      <TableHead key={s} className="text-right">
                        {t(`modules.status.${s}`)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {phases.map((phase) => {
                    const inPhase = all.filter((m) => m.phase === phase);
                    return (
                      <TableRow key={phase}>
                        <TableCell>{t(`modules.phase.${phase}`)}</TableCell>
                        {STATUSES.map((s) => (
                          <TableCell key={s} className="text-right font-mono">
                            {countBy(inPhase, s)}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              <ul className="flex flex-col gap-3">
                {modules.data.map((group) => {
                  const done = countBy(group.modules, 'disponible');
                  const building = countBy(group.modules, 'en_desarrollo');
                  return (
                    <li key={group.code} className="flex flex-col gap-1" data-testid={`panel-group-${group.code}`}>
                      <div className="flex flex-wrap justify-between gap-2 text-sm">
                        <span className="text-foreground">{group.name}</span>
                        <span className="text-muted-foreground">
                          {t('panel.groupProgress', { done, building, total: group.modules.length })}
                        </span>
                      </div>
                      <Progress
                        value={group.modules.length ? (done / group.modules.length) * 100 : 0}
                        aria-label={t('panel.groupProgressLabel', { group: group.name })}
                      />
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="panel-activity">
          <CardHeader>
            <CardTitle>{t('panel.activity')}</CardTitle>
          </CardHeader>
          <CardContent>
            {!activity.data ? (
              <Skeleton className="h-20 w-full" />
            ) : activity.data.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('panel.noActivity')}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {activity.data.map((a, i) => (
                  <li key={`${a.created_at}-${i}`} className="flex flex-col text-sm sm:flex-row sm:justify-between sm:gap-3">
                    <span className="text-foreground">{catalogLabel(t, 'audit.actions', a.action)}</span>
                    <span className="text-muted-foreground">
                      {a.user_name ?? t('settings.audit.system')} · {when(a.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card data-testid="panel-shortcuts">
          <CardHeader>
            <CardTitle>{t('panel.shortcuts')}</CardTitle>
          </CardHeader>
          <CardContent>
            {available.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('panel.noShortcuts')}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {available.map((m) => (
                  <li key={m.code}>
                    <Link className="text-sm text-brand underline-offset-4 hover:underline" to={moduleHref(m, material.id)}>
                      {m.name}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
