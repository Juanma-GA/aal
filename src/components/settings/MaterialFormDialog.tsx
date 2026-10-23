import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import type { Material, MaterialFields } from '@/types/auth';

interface Props {
  open: boolean;
  material: Material | null; // null: a new material
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: MaterialFields) => void;
}

interface FormValues {
  noc: string;
  name: string;
  part_number: string;
  ncage: string;
  grupo_clase: string;
  description: string;
}

const optional = (value: string): string | null => (value.trim() === '' ? null : value.trim());
// NOC and NCAGE are checked as the server checks them: upper case, without
// any space (NT 10/17 §9.1.3).
const code = (value: string): string => value.replace(/\s+/g, '').toUpperCase();

export function MaterialFormDialog({ open, material, onOpenChange, onSubmit }: Props): React.JSX.Element {
  const { t } = useTranslation();
  // The same formats the server checks (backend/app/schemas/materials.py).
  const schema = z.object({
    noc: z.string().transform(code).pipe(z.string().regex(/^([0-9A-Z]{13})?$/, t('validation.noc'))),
    name: z.string().trim().min(1, t('validation.required')).max(200, t('validation.maxLength', { max: 200 })),
    part_number: z.string().trim().max(32, t('validation.maxLength', { max: 32 })),
    ncage: z.string().transform(code).pipe(z.string().regex(/^([0-9A-Z]{5})?$/, t('validation.ncage'))),
    grupo_clase: z.string().transform(code).pipe(z.string().regex(/^([0-9]{4})?$/, t('validation.grupoClase'))),
    description: z.string().max(4000, t('validation.maxLength', { max: 4000 })),
  });
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });
  useEffect(() => {
    if (open) {
      form.reset({
        noc: material?.noc ?? '',
        name: material?.name ?? '',
        part_number: material?.part_number ?? '',
        ncage: material?.ncage ?? '',
        grupo_clase: material?.grupo_clase ?? '',
        description: material?.description ?? '',
      });
    }
  }, [open, material, form]);
  const submit = (v: FormValues) =>
    onSubmit({
      noc: optional(v.noc),
      name: v.name.trim(),
      part_number: optional(v.part_number),
      ncage: optional(v.ncage),
      grupo_clase: optional(v.grupo_clase),
      description: v.description,
    });
  const text = (name: keyof FormValues, mono = false) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{t(`material.fields.${name}`)}</FormLabel>
          <FormControl>
            <Input className={mono ? 'font-mono' : undefined} {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{material ? t('settings.materials.editTitle') : t('settings.materials.createTitle')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(submit)} className="flex flex-col gap-4" noValidate data-testid="material-form">
            {text('name')}
            {text('noc', true)}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {text('part_number', true)}
              {text('ncage', true)}
            </div>
            {text('grupo_clase', true)}
            {text('description')}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {t('actions.cancel')}
              </Button>
              <Button type="submit">{material ? t('actions.save') : t('actions.create')}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
