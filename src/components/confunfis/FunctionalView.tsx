import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SnsTree, type TreeSource } from '@/components/catalog/SnsTree';
import { Badge } from '@/components/ui/badge';
import { useConfunfisRows, useConfunfisSummary } from '@/hooks/useConfunfis';
import { fetchFunctional } from '@/services/confunfisApi';
import { positionOf, type FunctionalNode, type PositionRow } from '@/types/confunfis';
import { ObservationBadges } from './ObservationBadges';

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
  const rows = useConfunfisRows(materialId, { sns: selected ?? undefined }, 1);
  const outside = top.data?.outside ?? [];

  return (
    <div className="flex flex-col gap-4" data-testid="confunfis-functional">
      {summary.data ? (
        <div className="flex flex-wrap gap-2">
          <Badge data-testid="functional-covered">{t('confunfis.functional.covered', { covered: summary.data.sns_covered, total: summary.data.sns_in_config })}</Badge>
        </div>
      ) : null}
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
          dimmed={(n) => n.rows_below === 0}
          renderExtra={(n) => (n.row_count ? <Badge variant="secondary" className="shrink-0" data-testid={`functional-count-${n.sns}`}>{t('confunfis.functional.rows', { count: n.row_count })}</Badge> : null)}
        />
        <section className="flex flex-col gap-2 rounded-md border p-3 text-sm">
          {selected ? (
            <>
              <h3 className="font-medium"><span className="font-mono">{selected}</span></h3>
              {rows.data && rows.data.items.length === 0 ? <p className="text-muted-foreground">{t('confunfis.functional.empty')}</p> : null}
              <RowList rows={rows.data?.items ?? []} onSelect={onSelect} testId="functional-row" />
            </>
          ) : <p className="text-muted-foreground">{t('confunfis.functional.pick')}</p>}
        </section>
      </div>
    </div>
  );
}
