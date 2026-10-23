import { useTranslation } from 'react-i18next';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { Categories } from '@/types/catalog';

/** Categories -> subcategories of a version, with their number of SNS. */
export function CategoryPanel({ categories, selected, onSelect }: {
  categories: Categories | undefined;
  selected: string | null;
  onSelect: (code: string) => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  if (!categories) return <Skeleton className="h-60 w-full" />;
  return (
    <nav aria-label={t('catalog.categories')} className="flex flex-col gap-4" data-testid="catalog-categories">
      {categories.categories.map((c) => (
        <div key={c.code} className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase">
            <span className="font-mono">{c.code}</span> · {c.name}
          </p>
          <ul className="flex flex-col">
            {c.subcategories.map((s) => (
              <li key={s.code}>
                <button
                  type="button"
                  onClick={() => onSelect(s.code)}
                  aria-current={selected === s.code ? 'true' : undefined}
                  data-testid={`subcategory-${s.code}`}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                    selected === s.code ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
                  )}
                >
                  <span className="font-mono text-xs">{s.code}</span>
                  <span className="flex-1">{s.name}</span>
                  <span className="text-xs text-muted-foreground" aria-label={t('catalog.snsCount', { count: s.sns_count })}>
                    {s.sns_count}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {categories.uncategorized_rows ? (
        <p className="text-xs text-muted-foreground">{t('catalog.uncategorized', { count: categories.uncategorized_rows })}</p>
      ) : null}
    </nav>
  );
}
