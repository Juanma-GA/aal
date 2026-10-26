// The CONFUNFIS's physical tree (E13): the CUF (000000 01 00) at the top,
// each row under its higher assembly (CS). Loaded position by position
// (a row's children are asked for when it is opened) and virtualized. A
// hueco with alternatives (AL) groups them under a header; a row with
// alternative CS appears under each of them; the orphans (CS not found or
// badly formed) go to their own group.
import { useQueries } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { fetchTreeLevel } from '@/services/confunfisApi';
import { ROOT_POSITION, positionOf, type PositionRow, type TreeLevel } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';

const ROW_HEIGHT = 40;
const VIEW_HEIGHT = 600;
const OVERSCAN = 8;
const TOP = '__top__';
const ORPHANS = '__orphans__';

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
  const [open, setOpen] = useState<Set<string>>(() => new Set([`${TOP}/root`]));
  const [scrollTop, setScrollTop] = useState(0);

  // Every position whose children some open node shows.
  const positions = useMemo(() => {
    const out = new Set<string>([TOP]);
    for (const key of open) {
      const position = key.split('|').pop();
      if (position && !key.endsWith('/root') && key !== ORPHANS) out.add(position);
    }
    return [...out];
  }, [open]);
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
        if (open.has(key) && !seen.has(pos)) walk(pos, key, rowDepth + 1, new Set([...seen, pos]));
      }
    };
    if (top?.root) {
      const key = `${TOP}/root`;
      out.push({ kind: 'row', key, row: top.root, depth: 0 });
      if (open.has(key)) walk(ROOT_POSITION, key, 1, new Set([ROOT_POSITION]));
    } else {
      walk(ROOT_POSITION, TOP, 0, new Set([ROOT_POSITION]));
    }
    if (top && top.orphans.length) {
      out.push({ kind: 'orphans', key: ORPHANS, count: top.orphans.length, depth: 0 });
      if (open.has(ORPHANS)) for (const row of top.orphans) out.push({ kind: 'row', key: `${ORPHANS}/${row.id}|${positionOf(row)}`, row, depth: 1 });
    }
    return out;
    // byPosition is rebuilt from `levels` on each render: its data are the dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stamp, open, top]);

  if (!top) return <Skeleton className="h-96 w-full" />;
  const toggle = (key: string) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const first = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const last = Math.min(lines.length, Math.ceil((scrollTop + VIEW_HEIGHT) / ROW_HEIGHT) + OVERSCAN);

  return (
    <div className="flex flex-col gap-2">
      {top.cycles.length ? (
        <p className="text-sm text-destructive" role="alert" data-testid="tree-cycles">{t('confunfis.tree.cycles', { huecos: top.cycles.join(', ') })}</p>
      ) : null}
      <div
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
              const isOpen = open.has(line.key);
              return (
                <div key={line.key} role="treeitem" aria-level={1} aria-expanded={isOpen} className="absolute left-0 flex w-full items-center gap-2 border-t border-warning bg-muted text-sm font-medium" style={style}>
                  <button type="button" className="flex items-center gap-2" onClick={() => toggle(line.key)} data-testid="tree-orphans">
                    {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
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
            const isOpen = open.has(line.key);
            return (
              <div
                key={line.key}
                role="treeitem"
                aria-level={line.depth + 1}
                aria-expanded={row.child_count ? isOpen : undefined}
                aria-selected={selected === row.id}
                data-testid={`tree-row-${row.sns}-${row.co}-${row.al}`}
                className={cn('absolute left-0 flex w-full items-center gap-1 pr-2 text-sm', selected === row.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}
                style={style}
              >
                {row.child_count ? (
                  <button
                    type="button"
                    className="flex size-6 shrink-0 items-center justify-center rounded hover:bg-background"
                    aria-label={isOpen ? t('confunfis.tree.collapse', { position: positionOf(row) }) : t('confunfis.tree.expand', { position: positionOf(row) })}
                    onClick={() => toggle(line.key)}
                    data-testid={`tree-toggle-${row.sns}-${row.co}-${row.al}`}
                  >
                    {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
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
