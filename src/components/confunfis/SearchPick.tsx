// A text box with what it finds below (E13, shared since E14).
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const DEBOUNCE_MS = 250;

function useDebounced(value: string): string {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setOut(value.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [value]);
  return out;
}

export interface Pick<T> {
  id: string;
  label: string;
  value: T;
}

/** A text box with what it finds below; picking one sets it. */
export function SearchPick<T>({ id, label, placeholder, picked, onPick, onClear, search, testId }: {
  id: string;
  label: string;
  placeholder: string;
  picked: string | null;
  onPick: (value: T) => void;
  onClear?: () => void;
  search: (q: string) => Promise<Pick<T>[]>;
  testId: string;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const q = useDebounced(text);
  const found = useQuery({ queryKey: ['confunfis-pick', testId, q], queryFn: () => search(q), enabled: q.length > 0 });
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      {picked ? (
        <div className="flex items-center gap-2 text-sm" data-testid={`${testId}-picked`}>
          <span className="flex-1">{picked}</span>
          {onClear ? <Button variant="ghost" size="sm" onClick={onClear}>{t('confunfis.form.change')}</Button> : null}
        </div>
      ) : (
        <>
          <Input id={id} type="search" placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} data-testid={testId} />
          {q && found.data ? (
            <ul className="flex max-h-44 flex-col overflow-auto rounded-md border p-1" data-testid={`${testId}-results`}>
              {found.data.length === 0 ? <li className="px-2 py-1 text-xs text-muted-foreground">{t('confunfis.form.nothingFound')}</li> : null}
              {found.data.map((p) => (
                <li key={p.id}>
                  <button type="button" className="w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={() => { onPick(p.value); setText(''); }} data-testid={`${testId}-hit`}>
                    {p.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
    </div>
  );
}
