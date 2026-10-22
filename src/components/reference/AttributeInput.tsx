import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import type { AttributeSpec, AttributeValue } from '@/types/reference';

const NONE = '__none__';

/** The editor of one attribute, by its type: a list of its options, a
 *  yes/no switch, a number or a text. `undefined` is "no value". */
export function AttributeInput({ spec, value, onChange, id }: {
  spec: AttributeSpec;
  value: AttributeValue | undefined;
  onChange: (value: AttributeValue | undefined) => void;
  id: string;
}): React.JSX.Element {
  const { t } = useTranslation();
  if (spec.type === 'si_no') {
    return <Switch id={id} checked={value === true} onCheckedChange={(checked) => onChange(checked)} aria-label={spec.name} />;
  }
  if (spec.options.length) {
    return (
      <Select value={typeof value === 'string' ? value : NONE} onValueChange={(v) => onChange(v === NONE ? undefined : v)}>
        <SelectTrigger id={id} className="w-full" aria-label={spec.name}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {spec.required ? null : <SelectItem value={NONE}>{t('reference.none')}</SelectItem>}
          {spec.options.map((o) => (
            <SelectItem key={o.code} value={o.code}>
              {o.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (spec.type === 'entero') {
    return (
      <Input
        id={id}
        type="number"
        step={1}
        aria-label={spec.name}
        value={typeof value === 'number' ? String(value) : ''}
        onChange={(e) => onChange(e.target.value === '' ? undefined : Number.parseInt(e.target.value, 10))}
      />
    );
  }
  return (
    <Input id={id} aria-label={spec.name} value={typeof value === 'string' ? value : ''} onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value)} />
  );
}
