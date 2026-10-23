import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { SnsCard } from '@/components/catalog/SnsCard';
import { SnsTree } from '@/components/catalog/SnsTree';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { cufTree } from '@/lib/treeSources';
import { exportNormalized, searchNormalized } from '@/services/cufApi';
import type { SnsLevel } from '@/types/catalog';
import type { Cuf, NormalizedNode } from '@/types/cuf';

const LEVELS: SnsLevel[] = ['SISTEMA', 'SUBSISTEMA', 'SUBSUBSISTEMA', 'CONJUNTO', 'SUBCONJUNTO'];
const DEBOUNCE_MS = 300;

function Origins({ node }: { node: NormalizedNode }): React.JSX.Element {
  return (
    <span className="flex shrink-0 gap-1">
      {node.origins.map((o) => (
        <Badge key={o} variant="outline" className="font-mono text-xs" data-testid={`origin-${node.sns}-${o}`}>
          {o}
        </Badge>
      ))}
    </span>
  );
}

/** The CUF's normalized configuration: the "slots" its CONFUNFIS will
 *  fill. Figures by level, a search, the tree with the subcategory each SNS
 *  comes from, the SNS card and the Excel export (CONF_FUN, Anexo II). */
export function NormalizedConfigTab({ cuf }: { cuf: Cuf }): React.JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setQ(text.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const source = useMemo(() => cufTree(cuf.material_id, cuf.version), [cuf.material_id, cuf.version]);
  const results = useQuery({ queryKey: ['cuf', cuf.material_id, 'search', cuf.version, q], queryFn: () => searchNormalized(cuf.material_id, q, 1), enabled: q.length > 0 });
  const versionId = cuf.catalog_version?.id;
  if (!versionId || cuf.sns_count === 0) return <p className="text-sm text-muted-foreground">{t('cuf.emptyConfig')}</p>;
  const doExport = () =>
    exportNormalized(cuf.material_id)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? 'CONF_FUN.xlsx'))
      .catch((error: unknown) => notifyError(error, t));
  return (
    <div className="flex flex-col gap-4" data-testid="cuf-normalized">
      <p className="text-sm text-muted-foreground">{t('cuf.configHint')}</p>
      <div className="flex flex-wrap items-center gap-2" data-testid="cuf-levels">
        <Badge>{t('cuf.snsCount', { count: cuf.sns_count })}</Badge>
        {LEVELS.map((level) => (
          <Badge key={level} variant="secondary">
            {t(`catalog.levels.${level}`)}: {cuf.levels[level] ?? 0}
          </Badge>
        ))}
        <Button variant="outline" size="sm" className="sm:ml-auto" onClick={() => void doExport()} data-testid="cuf-export">
          {t('reference.export')}
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        <Input type="search" className="w-full sm:w-96" placeholder={t('catalog.search')} aria-label={t('catalog.search')} value={text} onChange={(e) => setText(e.target.value)} data-testid="cuf-search" />
        {q && results.data ? (
          <ul className="flex max-h-60 flex-col overflow-auto rounded-md border border-border p-2" data-testid="cuf-search-results">
            <li className="px-1 text-xs text-muted-foreground">{t('catalog.results', { count: results.data.total })}</li>
            {results.data.items.map((hit) => (
              <li key={hit.sns}>
                <button type="button" className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-sm hover:bg-muted" onClick={() => setSelected(hit.sns)} data-testid={`cuf-hit-${hit.sns}`}>
                  <span className="font-mono text-xs">{hit.sns}</span>
                  <span className="flex-1">{hit.name}</span>
                  <Origins node={hit} />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <SnsTree key={`${cuf.material_id}-${cuf.version}`} {...source} selected={selected} onSelect={setSelected} renderExtra={(node) => <Origins node={node} />} />
        <SnsCard
          versionId={versionId}
          sns={selected}
          onOpen={setSelected}
          onSubcategory={(code, sns) => navigate(`/configuracion-funcional?${new URLSearchParams({ v: versionId, sub: code, sns })}`)}
        />
      </div>
    </div>
  );
}
