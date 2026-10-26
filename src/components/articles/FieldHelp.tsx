import { CircleHelp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { ArticleField } from '@/types/reference';

/** The field's MAR06 help (the guide's own words): definition, purpose and
 *  remarks, with its MAR06 number and PRISMA code. */
export function FieldHelp({ field }: { field: ArticleField }): React.JSX.Element {
  const { t } = useTranslation();
  const help = field.help;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground"
          aria-label={t('articles.helpOf', { name: field.name })}
          data-testid={`help-${field.prisma_code}`}
        >
          <CircleHelp className="size-4" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96 text-sm" data-testid={`help-content-${field.prisma_code}`}>
        <p className="font-medium">
          {field.guide_field === 'N/A' ? t('articles.noMar06') : t('articles.mar06', { number: field.guide_field })} · <span className="font-mono">{field.prisma_code}</span>
          {help?.titulo ? ` · ${help.titulo}` : ''}
        </p>
        {help ? (
          <dl className="mt-2 flex flex-col gap-2">
            {(['definicion', 'finalidad', 'observaciones'] as const).map((key) =>
              help[key] ? (
                <div key={key}>
                  <dt className="text-xs font-medium text-muted-foreground">{t(`articles.help.${key}`)}</dt>
                  <dd className="whitespace-pre-wrap">{help[key]}</dd>
                </div>
              ) : null,
            )}
          </dl>
        ) : (
          <p className="mt-2 text-muted-foreground">{t('articles.noHelp')}</p>
        )}
      </PopoverContent>
    </Popover>
  );
}
