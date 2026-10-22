import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AttributeInput } from '@/components/reference/AttributeInput';
import { cleanAttributes } from '@/lib/attributes';
import { describeApiError } from '@/services/apiErrors';
import { createReferenceValue } from '@/services/referenceApi';
import type { AttributeValue, ReferenceTable } from '@/types/reference';

/** A new value of a table. Not optimistic: the id and the position come
 *  from the server (the documented exception of HR20 for creations). */
export function NewValueDialog({ table, open, onOpenChange, onCreated }: {
  table: ReferenceTable;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}): React.JSX.Element {
  const { t } = useTranslation();
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [definition, setDefinition] = useState('');
  const [attributes, setAttributes] = useState<Record<string, AttributeValue | undefined>>({});
  const create = useMutation({
    mutationFn: () =>
      createReferenceValue(table.code, { code: code.trim(), description: description.trim(), definition: definition.trim() || null, attributes: cleanAttributes(attributes) }),
    onSuccess: () => {
      onCreated();
      close(false);
    },
  });
  const close = (next: boolean) => {
    if (!next) {
      setCode('');
      setDescription('');
      setDefinition('');
      setAttributes({});
      create.reset();
    }
    onOpenChange(next);
  };
  const missing = !code.trim() || !description.trim() || table.attribute_schema.some((a) => a.required && attributes[a.key] === undefined);
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('reference.newValueTitle', { table: table.code })}</DialogTitle>
          <DialogDescription>{t('reference.newValueHint')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4" data-testid="new-value-form">
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-value-code">{t('reference.code')}</Label>
            <Input id="new-value-code" className="font-mono" value={code} onChange={(e) => setCode(e.target.value)} maxLength={30} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-value-description">{t('reference.description')}</Label>
            <Input id="new-value-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-value-definition">{t('reference.definition')}</Label>
            <Input id="new-value-definition" value={definition} onChange={(e) => setDefinition(e.target.value)} maxLength={2000} />
          </div>
          {table.attribute_schema.map((spec) => (
            <div key={spec.key} className="flex flex-col gap-2">
              <Label htmlFor={`new-value-attr-${spec.key}`}>{spec.name}</Label>
              <AttributeInput
                id={`new-value-attr-${spec.key}`}
                spec={spec}
                value={attributes[spec.key]}
                onChange={(v) => setAttributes((current) => ({ ...current, [spec.key]: v }))}
              />
            </div>
          ))}
          {create.error ? (
            <p className="text-sm text-destructive" role="alert">
              {describeApiError(create.error, t).message}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {t('actions.cancel')}
          </Button>
          <Button disabled={missing || create.isPending} onClick={() => create.mutate()} data-testid="new-value-save">
            {t('actions.create')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
