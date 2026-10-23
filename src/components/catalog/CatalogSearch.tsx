import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { searchSns } from '@/services/catalogApi';
import type { SearchHit } from '@/types/catalog';

const DEBOUNCE_MS = 300;

/** Search a whole version by code or name, page by page. */
export function CatalogSearch({ versionId, onPick }: { versionId: string; onPick: (hit: SearchHit) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(text.trim());
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const results = useQuery({ queryKey: ['catalog', versionId, 'search', q, page], queryFn: () => searchSns(versionId, q, page), enabled: q.length > 0 });
  const data = results.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <div className="relative flex flex-col gap-2">
      <Input
        type="search"
        placeholder={t('catalog.search')}
        aria-label={t('catalog.search')}
        value={text}
        onChange={(e) => setText(e.target.value)}
        data-testid="catalog-search"
        className="w-full sm:w-96"
      />
      {q && data ? (
        <div className="rounded-md border border-border bg-card p-2 shadow-sm" data-testid="catalog-search-results">
          <p className="px-1 pb-1 text-xs text-muted-foreground">{t('catalog.results', { count: data.total })}</p>
          <ul className="flex max-h-72 flex-col overflow-auto">
            {data.items.map((hit) => (
              <li key={hit.sns}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-sm hover:bg-muted"
                  onClick={() => {
                    onPick(hit);
                    setText('');
                    setQ('');
                  }}
                  data-testid={`search-hit-${hit.sns}`}
                >
                  <span className="font-mono text-xs">{hit.sns}</span>
                  <span className="flex-1">{hit.name}</span>
                  <span className="text-xs text-muted-foreground">{hit.subcategories.join(', ') || t('catalog.noSubcategory')}</span>
                </button>
              </li>
            ))}
          </ul>
          {pages > 1 ? (
            <div className="flex items-center justify-end gap-2 pt-1 text-xs">
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t('actions.previous')}
              </Button>
              {t('catalog.page', { page, pages })}
              <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                {t('actions.next')}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
