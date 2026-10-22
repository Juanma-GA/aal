import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import type { User } from '@/types/auth';

export interface UserFormValues {
  email: string;
  display_name: string;
  is_admin: boolean;
}

interface Props {
  open: boolean;
  user: User | null; // null: a new user
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: UserFormValues) => void;
}

export function UserFormDialog({ open, user, onOpenChange, onSubmit }: Props): React.JSX.Element {
  const { t } = useTranslation();
  const schema = z.object({
    email: z.string().trim().min(1, t('validation.required')).email(t('validation.email')),
    display_name: z.string().trim().min(1, t('validation.required')).max(200, t('validation.maxLength', { max: 200 })),
    is_admin: z.boolean(),
  });
  const form = useForm<UserFormValues>({ resolver: zodResolver(schema), defaultValues: { email: '', display_name: '', is_admin: false } });
  useEffect(() => {
    if (open) form.reset({ email: user?.email ?? '', display_name: user?.display_name ?? '', is_admin: user?.is_admin ?? false });
  }, [open, user, form]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{user ? t('settings.users.editTitle') : t('settings.users.createTitle')}</DialogTitle>
          {user ? null : <DialogDescription>{t('settings.users.createHint')}</DialogDescription>}
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate data-testid="user-form">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('settings.users.email')}</FormLabel>
                  <FormControl>
                    <Input type="email" disabled={user !== null} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('settings.users.name')}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="is_admin"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center gap-3">
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="font-normal">{t('settings.users.isAdmin')}</FormLabel>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {t('actions.cancel')}
              </Button>
              <Button type="submit">{user ? t('actions.save') : t('actions.create')}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
