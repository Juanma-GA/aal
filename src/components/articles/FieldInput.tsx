import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { isNumeric, isYesNo, tableOf } from '@/lib/articleFields';
import { cn } from '@/lib/utils';
import type { ArticleField, ReferenceValue } from '@/types/reference';

const EMPTY = '__empty__';

/** The input of a field, from its definition: S/N and table codes as a
 *  selector (code and name; a deactivated code only when it is the value),
 *  the rest as text or number. */
export function FieldInput({ field, value, onChange, values, disabled, invalid, id, compact }: {
  field: ArticleField;
  value: string | null;
  onChange: (value: string | null) => void;
  values?: ReferenceValue[];
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
  compact?: boolean;
}): React.JSX.Element {
  const { t } = useTranslation();
  const table = tableOf(field);
  const size = compact ? 'h-8 text-xs' : undefined;
  if (isYesNo(field) || table) {
    const options = isYesNo(field)
      ? (field.allowed_values ?? []).map((v) => ({ code: v, label: t(`articles.yesNo.${v}`, { defaultValue: v }) }))
      : (values ?? []).filter((v) => v.is_active || v.code === value).map((v) => ({ code: v.code, label: v.description }));
    const known = value === null || options.some((o) => o.code === value);
    return (
      <Select value={value ?? EMPTY} onValueChange={(v) => onChange(v === EMPTY ? null : v)} disabled={disabled}>
        <SelectTrigger id={id} aria-invalid={invalid || !known || undefined} className={cn('w-full', size)} data-testid={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={EMPTY}>{t('material.empty')}</SelectItem>
          {!known && value ? <SelectItem value={value}>{t('articles.unknownCode', { code: value })}</SelectItem> : null}
          {options.map((o) => (
            <SelectItem key={o.code} value={o.code}>
              <span className="font-mono">{o.code}</span> {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  return (
    <Input
      id={id}
      data-testid={id}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      disabled={disabled}
      inputMode={isNumeric(field) ? 'decimal' : undefined}
      aria-invalid={invalid || undefined}
      className={cn(isNumeric(field) ? 'text-right font-mono' : undefined, size)}
    />
  );
}
