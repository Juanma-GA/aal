import { useQuery } from '@tanstack/react-query';
import { Plus, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useSetSubcategories } from '@/hooks/useCuf';
import { fetchCategories } from '@/services/catalogApi';
import type { Cuf } from '@/types/cuf';

/** The subcategories of the CUF: removed from their chip, added from a
 *  picker of the version's categories with a search. The number of SNS of
 *  the normalized configuration updates with each change. */
export function SubcategoriesCard({ cuf, canEdit }: { cuf: Cuf; canEdit: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const versionId = cuf.catalog_version?.id ?? '';
  const categories = useQuery({ queryKey: ['catalog', versionId, 'categories'], queryFn: () => fetchCategories(versionId), enabled: Boolean(versionId) });
  const change = useSetSubcategories(cuf.material_id);
  const current = cuf.subcategories.map((s) => s.code);
  const needle = query.trim().toLocaleLowerCase('es');
  const options = (categories.data?.categories ?? [])
    .map((c) => ({
      ...c,
      subcategories: c.subcategories.filter(
        (s) => !current.includes(s.code) && (!needle || `${s.code} ${s.name} ${c.name}`.toLocaleLowerCase('es').includes(needle)),
      ),
    }))
    .filter((c) => c.subcategories.length);

  return (
    <Card data-testid="cuf-subcategories">
      <CardHeader>
        <CardTitle>{t('cuf.subcategories')}</CardTitle>
        <CardDescription data-testid="cuf-sns-count">
          {change.isPending ? t('cuf.recalculating') : t('cuf.snsCount', { count: cuf.sns_count })}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!cuf.catalog_version ? <p className="text-sm text-warning">{t('cuf.noCatalog')}</p> : null}
        <ul className="flex flex-wrap gap-2">
          {cuf.subcategories.length === 0 ? <li className="text-sm text-muted-foreground">{t('cuf.noSubcategories')}</li> : null}
          {cuf.subcategories.map((s) => (
            <li key={s.code}>
              <Badge variant="secondary" className="gap-1 py-1 text-sm" data-testid={`cuf-sub-${s.code}`}>
                <span className="font-mono">{s.code}</span> {s.name}
                {change.isPending ? null : <span className="text-muted-foreground">· {s.sns_count}</span>}
                {canEdit ? (
                  <button
                    type="button"
                    className="ml-1 rounded hover:text-destructive disabled:opacity-50"
                    // One change at a time: the next one needs the version the server gives back.
                    disabled={change.isPending}
                    aria-label={t('cuf.removeSubcategory', { code: s.code })}
                    data-testid={`cuf-remove-${s.code}`}
                    onClick={() => change.mutate({ cuf, codes: current.filter((c) => c !== s.code) })}
                  >
                    <X className="size-3" aria-hidden="true" />
                  </button>
                ) : null}
              </Badge>
            </li>
          ))}
        </ul>
        {canEdit && cuf.catalog_version ? (
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="self-start" data-testid="cuf-add-subcategory" disabled={change.isPending}>
                <Plus aria-hidden="true" />
                {t('cuf.addSubcategory')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-96">
              <Input placeholder={t('cuf.searchSubcategory')} aria-label={t('cuf.searchSubcategory')} value={query} onChange={(e) => setQuery(e.target.value)} className="mb-2" />
              <div className="flex max-h-72 flex-col gap-2 overflow-auto">
                {options.length === 0 ? <p className="text-sm text-muted-foreground">{t('cuf.noMoreSubcategories')}</p> : null}
                {options.map((c) => (
                  <div key={c.code}>
                    <p className="text-xs font-semibold text-muted-foreground uppercase">
                      <span className="font-mono">{c.code}</span> · {c.name}
                    </p>
                    {c.subcategories.map((s) => (
                      <button
                        key={s.code}
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-muted"
                        data-testid={`cuf-option-${s.code}`}
                        onClick={() => {
                          change.mutate({ cuf, codes: [...current, s.code], added: { code: s.code, name: s.name, category_code: c.code, category_name: c.name } });
                          setOpen(false);
                          setQuery('');
                        }}
                      >
                        <span className="font-mono text-xs">{s.code}</span>
                        <span className="flex-1">{s.name}</span>
                        <span className="text-xs text-muted-foreground">{t('catalog.snsCount', { count: s.sns_count })}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        ) : null}
      </CardContent>
    </Card>
  );
}
