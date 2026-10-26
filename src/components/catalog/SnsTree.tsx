// An SNS tree: a catalog subcategory's (E10) or a CUF's normalized
// configuration (E11). Loaded level by level (a node's children are asked
// for when it is opened, never the whole set) and virtualized (only the
// rows in view are in the page: the real catalog has subcategories with
// hundreds of SNS).
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { notifyError } from '@/lib/notify';
import { ancestors } from '@/lib/sns';
import { cn } from '@/lib/utils';
import type { TreeNode } from '@/types/catalog';

const ROW_HEIGHT = 34;
const VIEW_HEIGHT = 560;
const OVERSCAN = 8;
const ROOT = '__root__';

export interface TreeSource<N extends TreeNode> {
  /** Identifies the tree in the query cache. */
  cacheKey: readonly unknown[];
  /** The roots (no parent) or the children of `parent`. */
  loadLevel: (parent?: string) => Promise<N[]>;
}

type Props<N extends TreeNode> = TreeSource<N> & {
  selected: string | null;
  onSelect: (sns: string) => void;
  /** Extra marks after a node's name (the CUF's subcategories of origin). */
  renderExtra?: (node: N) => React.ReactNode;
  /** Nodes shown faded (E13: an SNS without CONFUNFIS rows). */
  dimmed?: (node: N) => boolean;
};

interface Visible<N> {
  node: N;
  depth: number;
}

export function SnsTree<N extends TreeNode>({ cacheKey, loadLevel, selected, onSelect, renderExtra, dimmed }: Props<N>): React.JSX.Element {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [levels, setLevels] = useState<Record<string, N[]>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [scrollTop, setScrollTop] = useState(0);
  const viewport = useRef<HTMLDivElement>(null);

  const load = useCallback(
    (parent: string) =>
      queryClient.fetchQuery({
        queryKey: [...cacheKey, parent],
        queryFn: () => loadLevel(parent === ROOT ? undefined : parent),
        staleTime: Infinity,
      }),
    // The caller memoizes both (a new tree is a new component, by key).
    [queryClient, cacheKey, loadLevel],
  );

  useEffect(() => {
    let alive = true;
    load(ROOT)
      .then((roots) => alive && setLevels({ [ROOT]: roots }))
      .catch((error: unknown) => notifyError(error, t));
    return () => {
      alive = false;
    };
  }, [load, t]);

  // An SNS chosen elsewhere (search, warnings, the card): its parents are
  // opened so it shows in the tree.
  const rootsLoaded = Boolean(levels[ROOT]);
  useEffect(() => {
    if (!selected || !rootsLoaded) return;
    const chain = ancestors(selected);
    let alive = true;
    Promise.all(chain.map((p) => load(p).then((nodes) => [p, nodes] as const)))
      .then((loaded) => {
        if (!alive) return;
        setLevels((current) => ({ ...current, ...Object.fromEntries(loaded) }));
        setOpen((current) => new Set([...current, ...chain]));
      })
      .catch((error: unknown) => notifyError(error, t));
    return () => {
      alive = false;
    };
  }, [selected, rootsLoaded, load, t]);

  const toggle = (node: N) => {
    if (open.has(node.sns)) {
      setOpen((current) => new Set([...current].filter((s) => s !== node.sns)));
      return;
    }
    load(node.sns)
      .then((children) => {
        setLevels((current) => ({ ...current, [node.sns]: children }));
        setOpen((current) => new Set([...current, node.sns]));
      })
      .catch((error: unknown) => notifyError(error, t));
  };

  const visible = useMemo(() => {
    const out: Visible<N>[] = [];
    const walk = (parent: string, depth: number) => {
      for (const node of levels[parent] ?? []) {
        out.push({ node, depth });
        if (open.has(node.sns)) walk(node.sns, depth + 1);
      }
    };
    walk(ROOT, 0);
    return out;
  }, [levels, open]);

  if (!levels[ROOT]) return <Skeleton className="h-96 w-full" />;
  const first = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const last = Math.min(visible.length, Math.ceil((scrollTop + VIEW_HEIGHT) / ROW_HEIGHT) + OVERSCAN);

  return (
    <div
      ref={viewport}
      role="tree"
      aria-label={t('catalog.tree')}
      data-testid="sns-tree"
      className="overflow-auto rounded-md border border-border"
      style={{ height: VIEW_HEIGHT }}
      onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
    >
      <div style={{ height: visible.length * ROW_HEIGHT, position: 'relative' }}>
        {visible.slice(first, last).map(({ node, depth }, i) => {
          const isOpen = open.has(node.sns);
          return (
            <div
              key={node.sns}
              role="treeitem"
              aria-level={depth + 1}
              aria-expanded={node.child_count ? isOpen : undefined}
              aria-selected={selected === node.sns}
              data-testid={`tree-node-${node.sns}`}
              className={cn(
                'absolute left-0 flex w-full items-center gap-1 pr-2 text-sm',
                selected === node.sns ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
                dimmed?.(node) && 'text-muted-foreground opacity-70',
              )}
              style={{ top: (first + i) * ROW_HEIGHT, height: ROW_HEIGHT, paddingLeft: 4 + depth * 16 }}
            >
              {node.child_count ? (
                <button
                  type="button"
                  className="flex size-6 shrink-0 items-center justify-center rounded hover:bg-background"
                  aria-label={isOpen ? t('catalog.collapse', { sns: node.sns }) : t('catalog.expand', { sns: node.sns })}
                  onClick={() => toggle(node)}
                  data-testid={`tree-toggle-${node.sns}`}
                >
                  {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                </button>
              ) : (
                <span className="size-6 shrink-0" />
              )}
              <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => onSelect(node.sns)}>
                <span className="font-mono text-xs">{node.sns}</span>
                <span className="truncate">{node.name}</span>
                {renderExtra ? renderExtra(node) : null}
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">{t(`catalog.levels.${node.level}`)}</span>
                {node.description_pending ? (
                  <Badge variant="outline" className="shrink-0 border-warning text-warning">
                    {t('catalog.pending')}
                  </Badge>
                ) : null}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
