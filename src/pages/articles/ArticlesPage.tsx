import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Plus } from 'lucide-react';
import { useDeferredValue, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArticleGrid } from '@/components/articles/ArticleGrid';
import { ExportDialog } from '@/components/articles/ExportDialog';
import { RevalidationPanel } from '@/components/articles/RevalidationPanel';
import { ImportWizard } from '@/components/import/ImportWizard';
import { NavRow } from '@/components/layout/NavRow';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useArticleList, useArticleRights, useCreateArticle } from '@/hooks/useArticles';
import { useFieldCodes } from '@/hooks/useFieldCodes';
import { useArticleFields } from '@/hooks/useReferenceTables';
import { describeApiError } from '@/services/apiErrors';
import { startArticleImport } from '@/services/articlesApi';
import { AR_RULES, type ArRule, type ArticleFilters, type ArticleTemplate } from '@/types/articles';
import { ARTICLES_PATH } from './ArticlePage';

const ALL = '__all__';
const WITH_FINDINGS = '__any__';
const ROW_HEIGHT = 49;
const VIEW_HEIGHT = 600;
const OVERSCAN = 8;
const TEMPLATES: ArticleTemplate[] = ['fichero_carga', 'maestro'];

function FilterSelect({ id, label, value, onChange, options }: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-44" data-testid={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{t('articles.all')}</SelectItem>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** "Artículos — datos básicos" (E12, RF-04): the single article master,
 *  common to every CUF (D16). A virtualized list with search, filters and a
 *  badge per AR rule broken; "Editar en rejilla"; import and export of the
 *  Fichero Carga and the Maestro AAL. Global like the catalog: it does not
 *  change the active material. */
export function ArticlesPage(): React.JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const rights = useArticleRights();
  const fields = useArticleFields();
  const codes = useFieldCodes(fields.data);
  const [q, setQ] = useState('');
  const query = useDeferredValue(q);
  const [rule, setRule] = useState(ALL);
  const [repairable, setRepairable] = useState(ALL);
  const [lifeControl, setLifeControl] = useState(ALL);
  const [group, setGroup] = useState(ALL);
  const [noNoc, setNoNoc] = useState(false);
  const [grid, setGrid] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState<ArticleTemplate | null>(null);
  const [exporting, setExporting] = useState<ArticleTemplate | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newNoc, setNewNoc] = useState('');
  const [scroll, setScroll] = useState(0);
  const create = useCreateArticle();
  const filters: ArticleFilters = useMemo(
    () => ({
      q: query || undefined,
      rule: rule !== ALL && rule !== WITH_FINDINGS ? (rule as ArRule) : undefined,
      with_findings: rule === WITH_FINDINGS ? true : undefined,
      repairable: repairable !== ALL ? (repairable as 'S' | 'N') : undefined,
      life_control: lifeControl !== ALL ? (lifeControl as 'S' | 'N') : undefined,
      group: group !== ALL ? group : undefined,
      no_noc: noNoc || undefined,
    }),
    [query, rule, repairable, lifeControl, group, noNoc],
  );
  const list = useArticleList(filters);
  const rows = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? 0;
  const canEdit = Boolean(rights.data?.can_edit);
  const nearEnd = () => {
    if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
  };
  const yesNo = [{ value: 'S', label: t('articles.yesNo.S') }, { value: 'N', label: t('articles.yesNo.N') }];
  const groups = (codes.D107 ?? []).map((v) => ({ value: v.code, label: `${v.code} · ${v.description}` }));
  const exportFilters: ArticleFilters = grid && selected.size ? { ids: [...selected] } : filters;

  const first = Math.max(0, Math.floor(scroll / ROW_HEIGHT) - OVERSCAN);
  const last = Math.min(rows.length, Math.ceil((scroll + VIEW_HEIGHT) / ROW_HEIGHT) + OVERSCAN);

  return (
    <div className="flex flex-col gap-6" data-testid="articles-page">
      <PageHeader crumbs={[{ label: t('articles.title') }]} title={t('articles.title')} />
      <p className="text-sm text-muted-foreground">{t('articles.hint')}</p>
      {rights.data?.can_import ? <RevalidationPanel /> : null}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-64 flex-1 flex-col gap-1">
          <Label htmlFor="article-search">{t('articles.search')}</Label>
          <Input id="article-search" data-testid="article-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('articles.searchHint')} />
        </div>
        <FilterSelect
          id="filter-rule"
          label={t('articles.filters.rule')}
          value={rule}
          onChange={setRule}
          options={[{ value: WITH_FINDINGS, label: t('articles.filters.withFindings') }, ...AR_RULES.map((r) => ({ value: r, label: `${r} · ${t(`articles.rules.${r}.title`)}` }))]}
        />
        <FilterSelect id="filter-repairable" label={t('articles.filters.repairable')} value={repairable} onChange={setRepairable} options={yesNo} />
        <FilterSelect id="filter-life" label={t('articles.filters.lifeControl')} value={lifeControl} onChange={setLifeControl} options={yesNo} />
        <FilterSelect id="filter-group" label={t('articles.filters.group')} value={group} onChange={setGroup} options={groups} />
        <div className="flex items-center gap-2 pb-2">
          <Checkbox id="filter-no-noc" checked={noNoc} onCheckedChange={(c) => setNoNoc(c === true)} />
          <Label htmlFor="filter-no-noc">{t('articles.filters.noNoc')}</Label>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-muted-foreground" data-testid="articles-total">
          {t('articles.total', { count: total })}
        </p>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          {canEdit ? (
            <Button variant={grid ? 'default' : 'outline'} onClick={() => { setGrid(!grid); setSelected(new Set()); }} data-testid="articles-grid-toggle">
              {grid ? t('articles.leaveGrid') : t('articles.editGrid')}
            </Button>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" data-testid="articles-export">
                {t('articles.export')}
                <ChevronDown aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {TEMPLATES.map((tpl) => (
                <DropdownMenuItem key={tpl} onSelect={() => setExporting(tpl)} data-testid={`articles-export-${tpl}`}>
                  {t(`articles.templates.${tpl}`)}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {rights.data?.can_import ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" data-testid="articles-import">
                  {t('articles.import')}
                  <ChevronDown aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {TEMPLATES.map((tpl) => (
                  <DropdownMenuItem key={tpl} onSelect={() => setImporting(tpl)} data-testid={`articles-import-${tpl}`}>
                    {t(`articles.templates.${tpl}`)}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          {canEdit ? (
            <Button onClick={() => { create.reset(); setNewName(''); setNewNoc(''); setCreating(true); }} data-testid="article-new">
              <Plus aria-hidden="true" />
              {t('articles.new')}
            </Button>
          ) : null}
        </div>
      </div>
      {!list.data || !fields.data ? (
        <Skeleton className="h-96 w-full" />
      ) : grid ? (
        <ArticleGrid rows={rows} fields={fields.data} codes={codes} onNearEnd={nearEnd} selected={selected} onSelected={setSelected} maxBatchRows={rights.data?.max_batch_rows ?? 1} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="articles-empty">{t('articles.empty')}</p>
      ) : (
        <div
          className="overflow-auto rounded-md border"
          style={{ height: Math.min(VIEW_HEIGHT, (rows.length + 1) * ROW_HEIGHT + 2) }}
          onScroll={(e) => {
            setScroll(e.currentTarget.scrollTop);
            if (e.currentTarget.scrollTop + VIEW_HEIGHT > (rows.length - 20) * ROW_HEIGHT) nearEnd();
          }}
          data-testid="articles-list"
        >
          <table className="w-full caption-bottom text-sm">
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead>{t('articles.columns.noc')}</TableHead>
                <TableHead>{t('articles.columns.name')}</TableHead>
                <TableHead>{t('articles.columns.group')}</TableHead>
                <TableHead>{t('articles.columns.repairable')}</TableHead>
                <TableHead>{t('articles.columns.lifeControl')}</TableHead>
                <TableHead>{t('articles.columns.findings')}</TableHead>
                <TableHead>
                  <span className="sr-only">{t('actions.open')}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              <tr style={{ height: first * ROW_HEIGHT }} />
              {rows.slice(first, last).map((a) => (
                <NavRow key={a.id} to={`${ARTICLES_PATH}/${a.id}`} label={t('articles.open', { name: a.nombre })} data-testid={`article-row-${a.nombre}`} style={{ height: ROW_HEIGHT }}>
                  <TableCell className="font-mono text-xs">{a.noc ?? <span className="text-warning">{t('articles.provisional')}</span>}</TableCell>
                  <TableCell className="whitespace-normal font-medium">{a.nombre}</TableCell>
                  <TableCell>{a.fields.cdConjRep ?? t('material.empty')}</TableCell>
                  <TableCell>{a.fields.snRepaArt ?? t('material.empty')}</TableCell>
                  <TableCell>{a.fields.snCtrlVidaArt ?? t('material.empty')}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {a.finding_codes.map((code) => (
                        <Badge key={code} variant="outline" title={t(`articles.rules.${code}.title`)} data-testid={`row-badge-${code}`}>
                          {code}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                </NavRow>
              ))}
              <tr style={{ height: Math.max(0, rows.length - last) * ROW_HEIGHT }} />
            </tbody>
          </table>
        </div>
      )}
      {importing ? (
        <ImportWizard
          open
          onOpenChange={(open) => !open && setImporting(null)}
          title={t('articles.importTitle', { template: t(`articles.templates.${importing}`) })}
          start={(file) => startArticleImport(importing, file)}
          onApplied={() => void queryClient.invalidateQueries({ queryKey: ['articles'] })}
          fieldNames={Object.fromEntries((fields.data ?? []).map((f) => [f.prisma_code, f.name]))}
        />
      ) : null}
      <ExportDialog template={exporting} filters={exportFilters} onOpenChange={(open) => !open && setExporting(null)} />
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent data-testid="article-new-form">
          <DialogHeader>
            <DialogTitle>{t('articles.newTitle')}</DialogTitle>
            <DialogDescription>{t('articles.newHint')}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="new-name">{fields.data?.find((f) => f.prisma_code === 'NomArt')?.name}</Label>
              <Input id="new-name" value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={40} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="new-noc">{fields.data?.find((f) => f.prisma_code === 'cdART')?.name}</Label>
              <Input id="new-noc" className="font-mono" value={newNoc} onChange={(e) => setNewNoc(e.target.value)} />
            </div>
            {create.error ? (
              <p className="text-sm text-destructive" role="alert">
                {describeApiError(create.error, t).message}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)}>
              {t('actions.cancel')}
            </Button>
            <Button
              disabled={!newName.trim() || create.isPending}
              onClick={() => create.mutate({ nombre: newName.trim(), noc: newNoc.trim() || null }, { onSuccess: (a) => navigate(`${ARTICLES_PATH}/${a.id}`) })}
              data-testid="article-new-save"
            >
              {t('actions.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
