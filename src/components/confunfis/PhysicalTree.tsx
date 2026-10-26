// The CONFUNFIS's physical tree (E13): the CUF (000000 01 00) at the top,
// each row under its higher assembly (CS). Loaded position by position
// (a row's children are asked for when it is opened) and virtualized. A
// hueco with alternatives (AL) groups them under a header; a row with
// alternative CS appears under each of them; the orphans (CS not found or
// badly formed) go to their own group. (E14) A search by SNS, name, NOC or
// P/N opens the path to each hit and walks them ("3 de 7"); "Expandir todo"
// opens every level as it loads.
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronLeft, ChevronRight, ChevronsDownUp, ChevronsUpDown } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { fetchTreeLevel, searchTree } from '@/services/confunfisApi';
import { ROOT_POSITION, positionOf, type PositionRow, type TreeLevel, type TreeSearch } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';

const ROW_HEIGHT = 40;
const VIEW_HEIGHT = 600;
const OVERSCAN = 8;
const TOP = '__top__';
const ORPHANS = '__orphans__';
const ROOT_KEY = `${TOP}/root`;
const DEBOUNCE_MS = 300;

const rowKeyOf = (parent: string, row: { id: string; position: string }) => `${parent}/${row.id}|${row.position}`;

/** The node keys from the top down to a hit, and the hit's own key. */
function keysOf(hit: TreeSearch['hits'][number], hasRoot: boolean): { open: string[]; key: string } {
  const position = positionOf(hit.row);
  if (hit.row.orphan) return { open: [ORPHANS], key: rowKeyOf(ORPHANS, { id: hit.row.id, position }) };
  if (hasRoot && position === ROOT_POSITION) return { open: [], key: ROOT_KEY };
  const open: string[] = [];
  let parent = TOP;
  for (const step of hit.path) {
    parent = step.position === ROOT_POSITION && hasRoot ? ROOT_KEY : rowKeyOf(parent, step);
    open.push(parent);
  }
  if (hit.path.length === 0 && hasRoot) {
    open.push(ROOT_KEY);
    parent = ROOT_KEY;
  }
  return { open, key: rowKeyOf(parent, { id: hit.row.id, position }) };
}

type Line =
  | { kind: 'row'; key: string; row: PositionRow; depth: number }
  | { kind: 'hueco'; key: string; sns: string; co: string; name: string | null; count: number; qty: string | null; total: string | null; depth: number }
  | { kind: 'orphans'; key: string; count: number; depth: number };

interface Props {
  materialId: string;
  selected: string | null;
  onSelect: (row: PositionRow) => void;
}

export function PhysicalTree({ materialId, selected, onSelect }: Props): React.JSX.Element {
  const { t } = useTranslation();
  // Open nodes by their path (a row may hang from two CS: two paths).
  const [open, setOpen] = useState<Set<string>>(() => new Set([ROOT_KEY]));
  // "Expandir todo": every node open but those closed by hand.
  const [expandAll, setExpandAll] = useState(false);
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const [scrollTop, setScrollTop] = useState(0);
  const viewport = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  // The search, and the hit shown.
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => { setQ(text.trim()); setCurrent(0); }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const found = useQuery({ queryKey: ['confunfis', materialId, 'search', q], queryFn: () => searchTree(materialId, q), enabled: q.length > 0 });
  const hits = q && found.data ? found.data.hits : [];

  const hit = hits.length ? hits[Math.min(current, hits.length - 1)] : null;
  const topLevel = queryClient.getQueryData<TreeLevel>(['confunfis', materialId, 'tree', TOP]);
  const target = hit && topLevel ? keysOf(hit, Boolean(topLevel.root)) : null;
  const targetKey = target?.key ?? null;
  const isOpen = (key: string) => Boolean(target?.open.includes(key)) || (expandAll ? !closed.has(key) : open.has(key));

  // Every position whose children some open node shows; expanding all,
  // every position with children among the levels already loaded.
  const fromKeys = new Set<string>([TOP]);
  for (const key of [...open, ...(target?.open ?? [])]) {
    const position = key.split('|').pop();
    if (position && key !== ROOT_KEY && key !== ORPHANS && !key.endsWith('/root')) fromKeys.add(position);
  }
  if (expandAll) {
    for (const [, data] of queryClient.getQueriesData<TreeLevel>({ queryKey: ['confunfis', materialId, 'tree'] })) {
      for (const r of data?.items ?? []) if (r.child_count) fromKeys.add(positionOf(r));
    }
  }
  const positions = [...fromKeys];
  const levels = useQueries({
    queries: positions.map((p) => ({
      queryKey: ['confunfis', materialId, 'tree', p],
      queryFn: () => fetchTreeLevel(materialId, p === TOP ? undefined : p),
      staleTime: 30_000,
    })),
  });
  const byPosition = new Map<string, TreeLevel>();
  positions.forEach((p, i) => {
    const data = levels[i]?.data;
    if (data) byPosition.set(p, data);
  });
  const top = byPosition.get(TOP);
  const stamp = levels.map((l) => l.dataUpdatedAt).join('|');

  const lines = useMemo(() => {
    const out: Line[] = [];
    const walk = (position: string, path: string, depth: number, seen: Set<string>) => {
      const level = position === ROOT_POSITION ? (byPosition.get(TOP) ?? byPosition.get(ROOT_POSITION)) : byPosition.get(position);
      if (!level) return;
      const items = level.items;
      for (let i = 0; i < items.length; i++) {
        const row = items[i];
        const same = items.filter((r) => r.sns === row.sns && r.co === row.co);
        const grouped = same.length > 1 && same.some((r) => r.alternative);
        if (grouped && same[0] === row) {
          out.push({ kind: 'hueco', key: `${path}/h:${row.sns}${row.co}`, sns: row.sns, co: row.co, name: row.sns_name, count: same.length, qty: row.qty, total: row.total, depth });
        }
        const rowDepth = grouped ? depth + 1 : depth;
        const key = `${path}/${row.id}|${positionOf(row)}`;
        out.push({ kind: 'row', key, row, depth: rowDepth });
        const pos = positionOf(row);
        if (isOpen(key) && !seen.has(pos)) walk(pos, key, rowDepth + 1, new Set([...seen, pos]));
      }
    };
    if (top?.root) {
      out.push({ kind: 'row', key: ROOT_KEY, row: top.root, depth: 0 });
      if (isOpen(ROOT_KEY)) walk(ROOT_POSITION, ROOT_KEY, 1, new Set([ROOT_POSITION]));
    } else {
      walk(ROOT_POSITION, TOP, 0, new Set([ROOT_POSITION]));
    }
    if (top && top.orphans.length) {
      out.push({ kind: 'orphans', key: ORPHANS, count: top.orphans.length, depth: 0 });
      if (isOpen(ORPHANS)) for (const row of top.orphans) out.push({ kind: 'row', key: `${ORPHANS}/${row.id}|${positionOf(row)}`, row, depth: 1 });
    }
    return out;
    // byPosition is rebuilt from `levels` on each render: its data are the dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stamp, open, top, expandAll, closed, targetKey]);

  // The hit shown: its path stays open while it is the one shown.
  const targetIndex = targetKey ? lines.findIndex((l) => l.key === targetKey) : -1;
  useEffect(() => {
    if (targetIndex < 0 || !viewport.current) return;
    viewport.current.scrollTop = Math.max(0, targetIndex * ROW_HEIGHT - VIEW_HEIGHT / 3);
  }, [targetIndex]);

  if (!top) return <Skeleton className="h-96 w-full" />;
  const toggle = (key: string) => {
    const update = (c: Set<string>) => {
      const next = new Set(c);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    };
    if (expandAll) setClosed(update);
    else setOpen(update);
  };
  const go = (step: number) => setCurrent((c) => (hits.length ? (c + step + hits.length) % hits.length : 0));
  const first = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const last = Math.min(lines.length, Math.ceil((scrollTop + VIEW_HEIGHT) / ROW_HEIGHT) + OVERSCAN);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search" className="w-full sm:w-80" value={text} onChange={(e) => setText(e.target.value)}
          placeholder={t('confunfis.tree.searchHint')} aria-label={t('confunfis.tree.search')} data-testid="tree-search"
        />
        {q ? (
          <>
            <span className="text-sm text-muted-foreground" data-testid="tree-search-count" role="status">
              {hits.length ? t('confunfis.tree.hitOf', { n: Math.min(current, hits.length - 1) + 1, m: hits.length }) : t('confunfis.tree.noHits')}
            </span>
            <Button variant="outline" size="icon" disabled={hits.length < 2} onClick={() => go(-1)} aria-label={t('confunfis.tree.previousHit')} data-testid="tree-search-previous">
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Button variant="outline" size="icon" disabled={hits.length < 2} onClick={() => go(1)} aria-label={t('confunfis.tree.nextHit')} data-testid="tree-search-next">
              <ChevronRight aria-hidden="true" />
            </Button>
          </>
        ) : null}
        <div className="flex gap-2 sm:ml-auto">
          <Button variant="outline" size="sm" onClick={() => { setExpandAll(true); setClosed(new Set()); }} data-testid="tree-expand-all">
            <ChevronsUpDown aria-hidden="true" />
            {t('confunfis.tree.expandAll')}
          </Button>
          <Button variant="outline" size="sm" onClick={() => { setExpandAll(false); setOpen(new Set([ROOT_KEY])); }} data-testid="tree-collapse-all">
            <ChevronsDownUp aria-hidden="true" />
            {t('confunfis.tree.collapseAll')}
          </Button>
        </div>
      </div>
      {top.cycles.length ? (
        <p className="text-sm text-destructive" role="alert" data-testid="tree-cycles">{t('confunfis.tree.cycles', { huecos: top.cycles.join(', ') })}</p>
      ) : null}
      <div
        ref={viewport}
        role="tree"
        aria-label={t('confunfis.tree.label')}
        data-testid="physical-tree"
        className="overflow-auto rounded-md border border-border"
        style={{ height: VIEW_HEIGHT }}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <div style={{ height: lines.length * ROW_HEIGHT, position: 'relative' }}>
          {lines.slice(first, last).map((line, i) => {
            const style = { top: (first + i) * ROW_HEIGHT, height: ROW_HEIGHT, paddingLeft: 4 + line.depth * 18 };
            if (line.kind === 'orphans') {
              const lineOpen = isOpen(line.key);
              return (
                <div key={line.key} role="treeitem" aria-level={1} aria-expanded={lineOpen} className="absolute left-0 flex w-full items-center gap-2 border-t border-warning bg-muted text-sm font-medium" style={style}>
                  <button type="button" className="flex items-center gap-2" onClick={() => toggle(line.key)} data-testid="tree-orphans">
                    {lineOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                    {t('confunfis.tree.orphans', { count: line.count })}
                  </button>
                </div>
              );
            }
            if (line.kind === 'hueco') {
              return (
                <div key={line.key} role="treeitem" aria-level={line.depth + 1} className="absolute left-0 flex w-full items-center gap-2 pr-2 text-sm text-muted-foreground" style={style} data-testid={`tree-hueco-${line.sns}-${line.co}`}>
                  <span className="size-6 shrink-0" />
                  <span className="font-mono text-xs">{line.sns} {line.co}</span>
                  <span className="truncate">{line.name}</span>
                  <Badge variant="outline">{t('confunfis.tree.alternatives', { count: line.count })}</Badge>
                  <span className="ml-auto shrink-0 text-xs">{t('confunfis.tree.qtyTotal', { qty: line.qty ?? '—', total: line.total ?? '—' })}</span>
                </div>
              );
            }
            const { row } = line;
            const lineOpen = isOpen(line.key);
            return (
              <div
                key={line.key}
                role="treeitem"
                aria-level={line.depth + 1}
                aria-expanded={row.child_count ? lineOpen : undefined}
                aria-selected={selected === row.id}
                data-testid={`tree-row-${row.sns}-${row.co}-${row.al}`}
                className={cn(
                  'absolute left-0 flex w-full items-center gap-1 pr-2 text-sm',
                  selected === row.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
                  line.key === targetKey && 'ring-2 ring-inset ring-ring',
                )}
                data-hit={line.key === targetKey ? 'true' : undefined}
                style={style}
              >
                {row.child_count ? (
                  <button
                    type="button"
                    className="flex size-6 shrink-0 items-center justify-center rounded hover:bg-background"
                    aria-label={lineOpen ? t('confunfis.tree.collapse', { position: positionOf(row) }) : t('confunfis.tree.expand', { position: positionOf(row) })}
                    onClick={() => toggle(line.key)}
                    data-testid={`tree-toggle-${row.sns}-${row.co}-${row.al}`}
                  >
                    {lineOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                  </button>
                ) : (
                  <span className="size-6 shrink-0" />
                )}
                <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => onSelect(row)}>
                  <span className="shrink-0 font-mono text-xs">{positionOf(row)}</span>
                  <span className="truncate">{row.article_name ?? row.article?.nombre ?? t('confunfis.noName')}</span>
                  {row.article?.noc ? <span className="hidden shrink-0 font-mono text-xs text-muted-foreground lg:inline">{row.article.noc}</span> : null}
                  {row.alternative ? <Badge variant="outline" className="shrink-0">{t('confunfis.badges.alternative')}</Badge> : null}
                  {row.cs_alternative ? <Badge variant="outline" className="shrink-0">{t('confunfis.badges.csAlternative')}</Badge> : null}
                  {row.ct_sigle === 'S' ? <Badge variant="secondary" className="shrink-0">{t('confunfis.badges.ctSigle')}</Badge> : null}
                  <ObservationBadges row={row} compact />
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground" data-testid={`tree-total-${row.sns}-${row.co}-${row.al}`}>
                    {t('confunfis.tree.qtyTotal', { qty: row.qty ?? '—', total: row.total ?? '—' })}
                  </span>
                </button>
                {row.is_mounted ? (
                  row.mounted ? (
                    <Link to={`/materiales/${row.mounted.id}/confunfis`} className="shrink-0 text-xs text-link underline-offset-2 hover:underline" data-testid={`tree-mounted-${row.sns}`}>
                      {t('confunfis.badges.mounted')}
                    </Link>
                  ) : (
                    <Badge variant="outline" className="shrink-0">{t('confunfis.badges.mounted')}</Badge>
                  )
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
