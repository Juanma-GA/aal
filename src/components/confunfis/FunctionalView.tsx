import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SnsTree, type TreeSource } from '@/components/catalog/SnsTree';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useConfunfisRows, useConfunfisSummary } from '@/hooks/useConfunfis';
import { fetchFunctional } from '@/services/confunfisApi';
import { searchNormalized } from '@/services/cufApi';
import { positionOf, type FunctionalNode, type PositionRow } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';

const DEBOUNCE_MS = 300;

function RowList({ rows, onSelect, testId }: { rows: PositionRow[]; onSelect: (row: PositionRow) => void; testId: string }): React.JSX.Element {
  return (
    <ul className="flex flex-col" data-testid={testId}>
      {rows.map((r) => (
        <li key={r.id}>
          <button type="button" className="flex w-full flex-wrap items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={() => onSelect(r)} data-testid={`${testId}-${r.sns}`}>
            <span className="font-mono text-xs">{positionOf(r)}</span>
            <span className="flex-1">{r.article_name}</span>
            <ObservationBadges row={r} compact />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** "¿Qué funciones he cubierto?" (E13): the CUF's normalized configuration
 *  (E10/E11) with the CONFUNFIS rows of each SNS -- the empty ones faded --
 *  and, apart and highlighted, the rows whose SNS is not in it. */
export function FunctionalView({ materialId, onSelect }: { materialId: string; onSelect: (row: PositionRow) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const summary = useConfunfisSummary(materialId);
  const stamp = summary.dataUpdatedAt;
  const top = useQuery({ queryKey: ['confunfis', materialId, 'functional', 'top', stamp], queryFn: () => fetchFunctional(materialId) });
  const source = useMemo<TreeSource<FunctionalNode>>(
    () => ({ cacheKey: ['confunfis-functional', materialId, stamp], loadLevel: (parent) => fetchFunctional(materialId, parent).then((l) => l.items) }),
    [materialId, stamp],
  );
  const [selected, setSelected] = useState<string | null>(null);
  // (E14) The search: SNS or name in the configuration, walked "n de m".
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => { setQ(text.trim()); setCurrent(0); }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const found = useQuery({ queryKey: ['confunfis', materialId, 'functional-search', q], queryFn: () => searchNormalized(materialId, q, 1), enabled: q.length > 0 });
  const hits = q && found.data ? found.data.items : [];
  const go = (step: number) => {
    if (!hits.length) return;
    // The first press shows the hit counted ("1 de n"); the next ones move.
    const shown = hits[Math.min(current, hits.length - 1)].sns === selected;
    const next = shown ? (current + step + hits.length) % hits.length : Math.min(current, hits.length - 1);
    setCurrent(next);
    setSelected(hits[next].sns);
  };
  const rows = useConfunfisRows(materialId, { sns: selected ?? undefined }, 1);
  const holders = useConfunfisRows(materialId, { extra_sns: selected ?? undefined }, 1, Boolean(selected));
  const outside = top.data?.outside ?? [];

  return (
    <div className="flex flex-col gap-4" data-testid="confunfis-functional">
      {summary.data ? (
        <div className="flex flex-wrap gap-2">
          <Badge data-testid="functional-covered">{t('confunfis.functional.covered', { covered: summary.data.sns_covered, total: summary.data.sns_in_config })}</Badge>
          {summary.data.sns_covered_by_extra ? (
            <Badge variant="outline" className="border-dashed border-link text-link">{t('confunfis.functional.coveredOnlyByExtra', { count: summary.data.sns_covered_by_extra })}</Badge>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search" className="w-full sm:w-80" value={text} placeholder={t('confunfis.functional.searchHint')} aria-label={t('confunfis.tree.search')}
          onChange={(e) => setText(e.target.value)} data-testid="functional-search"
          onKeyDown={(e) => { if (e.key === 'Enter' && hits.length) setSelected(hits[Math.min(current, hits.length - 1)].sns); }}
        />
        {q ? (
          <>
            <span className="text-sm text-muted-foreground" role="status" data-testid="functional-search-count">
              {hits.length ? t('confunfis.tree.hitOf', { n: Math.min(current, hits.length - 1) + 1, m: found.data?.total ?? hits.length }) : t('confunfis.tree.noHits')}
            </span>
            <Button variant="outline" size="icon" disabled={!hits.length} onClick={() => go(-1)} aria-label={t('confunfis.tree.previousHit')}>
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Button variant="outline" size="icon" disabled={!hits.length} onClick={() => go(1)} aria-label={t('confunfis.tree.nextHit')}>
              <ChevronRight aria-hidden="true" />
            </Button>
          </>
        ) : null}
      </div>
      {outside.length ? (
        <section className="rounded-md border border-warning p-3" data-testid="functional-outside">
          <h3 className="mb-1 text-sm font-medium text-warning">{t('confunfis.functional.outside', { count: outside.length })}</h3>
          <RowList rows={outside} onSelect={onSelect} testId="functional-outside-row" />
        </section>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <SnsTree<FunctionalNode>
          key={stamp}
          {...source}
          selected={selected}
          onSelect={setSelected}
          dimmed={(n) => n.rows_below === 0 && n.extras_below === 0}
          renderExtra={(n) => (
            <>
              {n.row_count ? <Badge variant="secondary" className="shrink-0" data-testid={`functional-count-${n.sns}`}>{t('confunfis.functional.rows', { count: n.row_count })}</Badge> : null}
              {/* E14: covered by the extra function of a row elsewhere; alone, it is the only cover. */}
              {n.extra_count ? (
                <Badge variant="outline" className={n.row_count ? 'shrink-0' : 'shrink-0 border-dashed border-link text-link'} data-testid={`functional-extra-${n.sns}`}>
                  {t('confunfis.functional.byExtra', { count: n.extra_count })}
                </Badge>
              ) : null}
            </>
          )}
        />
        <section className="flex flex-col gap-2 rounded-md border p-3 text-sm">
          {selected ? (
            <>
              <h3 className="font-medium"><span className="font-mono">{selected}</span></h3>
              {rows.data && rows.data.items.length === 0 ? <p className="text-muted-foreground">{t('confunfis.functional.empty')}</p> : null}
              <RowList rows={rows.data?.items ?? []} onSelect={onSelect} testId="functional-row" />
              {holders.data?.items.length ? (
                <>
                  <h4 className="mt-2 text-xs font-medium text-muted-foreground">{t('confunfis.functional.coveredByExtra')}</h4>
                  <RowList rows={holders.data.items} onSelect={onSelect} testId="functional-extra-row" />
                </>
              ) : null}
            </>
          ) : <p className="text-muted-foreground">{t('confunfis.functional.pick')}</p>}
        </section>
      </div>
    </div>
  );
}
