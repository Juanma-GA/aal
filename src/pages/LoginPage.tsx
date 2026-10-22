import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { SystemStatusCard } from '@/components/SystemStatusCard';
import { login } from '@/services/authApi';
import { describeApiError } from '@/services/apiErrors';
import { useAuthStore } from '@/stores/authStore';

export function LoginPage(): React.JSX.Element {
  const { t } = useTranslation();
  const status = useAuthStore((s) => s.status);
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [error, setError] = useState<{ message: string; reference: string | null } | null>(null);
  const schema = z.object({
    email: z.string().trim().min(1, t('validation.required')),
    password: z.string().min(1, t('validation.required')),
  });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } });
  const from = (location.state as { from?: string } | null)?.from ?? '/';

  if (status === 'signedIn') return <Navigate to={from} replace />;

  const onSubmit = async (values: z.infer<typeof schema>) => {
    setError(null);
    try {
      // The result is the server's (a token): nothing to show before it.
      await login(values.email, values.password);
      // Another user may have been signed in: nothing of theirs stays.
      await queryClient.resetQueries();
      navigate(from, { replace: true });
    } catch (err) {
      setError(describeApiError(err, t));
      form.resetField('password');
    }
  };

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{t('auth.loginTitle')}</CardTitle>
          <CardDescription>{t('auth.loginDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.email')}</FormLabel>
                    <FormControl>
                      <Input type="email" autoComplete="username" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.password')}</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {error ? (
                <Alert variant="destructive" data-testid="login-error">
                  <AlertDescription>
                    {error.message}
                    {error.reference ? <span className="block font-mono text-xs">{error.reference}</span> : null}
                  </AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? t('auth.signingIn') : t('actions.signIn')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
      <SystemStatusCard />
    </div>
  );
}
