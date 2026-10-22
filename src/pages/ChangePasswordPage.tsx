import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { meKey, useMe } from '@/hooks/useSession';
import { changePassword } from '@/services/authApi';
import { describeApiError } from '@/services/apiErrors';

export function ChangePasswordPage(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const schema = z
    .object({
      current: z.string().min(1, t('validation.required')),
      next: z.string().min(1, t('validation.required')),
      repeat: z.string().min(1, t('validation.required')),
    })
    .refine((v) => v.next === v.repeat, { path: ['repeat'], message: t('auth.passwordsDiffer') });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { current: '', next: '', repeat: '' } });
  const forced = me.data?.must_change_password ?? false;

  const onSubmit = async (values: z.infer<typeof schema>) => {
    setError(null);
    try {
      // The password policy is the server's (parameter auth.password): it
      // answers with the rule that failed.
      await changePassword(values.current, values.next);
      await queryClient.invalidateQueries({ queryKey: meKey });
      toast.success(t('auth.changed'));
      navigate('/', { replace: true });
    } catch (err) {
      setError(describeApiError(err, t).message);
    }
  };

  const field = (name: 'current' | 'next' | 'repeat', label: string, autoComplete: string) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field: f }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input type="password" autoComplete={autoComplete} {...f} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{t('auth.changeTitle')}</CardTitle>
          <CardDescription>{forced ? t('auth.changeRequired') : t('auth.changeDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate data-testid="change-password-form">
              {field('current', t('auth.currentPassword'), 'current-password')}
              {field('next', t('auth.newPassword'), 'new-password')}
              {field('repeat', t('auth.repeatPassword'), 'new-password')}
              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {t('actions.changePassword')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
