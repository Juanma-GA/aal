import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useHealth, useVersion } from '@/hooks/useSystemStatus';
import { describeApiError } from '@/services/apiErrors';
import type { MigrationStatus } from '@/types/system';

function MigrationText({ migrations }: { migrations: MigrationStatus }): React.JSX.Element {
  const { t } = useTranslation();
  if (!migrations.current) return <>{t('status.migrationNone')}</>;
  if (migrations.up_to_date) return <>{t('status.migrationUpToDate', { current: migrations.current })}</>;
  return <>{t('status.migrationBehind', { current: migrations.current, head: migrations.head })}</>;
}

function Row({ label, children, testId }: { label: string; children: React.ReactNode; testId: string }): React.JSX.Element {
  return (
    <div className="flex flex-col gap-1 border-t py-3 first:border-t-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-mono text-sm text-foreground" data-testid={testId}>
        {children}
      </dd>
    </div>
  );
}

export function HomePage(): React.JSX.Element {
  const { t } = useTranslation();
  const health = useHealth();
  const version = useVersion();
  const error = health.error ?? version.error;

  const retry = () => {
    void health.refetch();
    void version.refetch();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">{t('home.title')}</CardTitle>
        <CardDescription>{t('home.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <ErrorState error={error} onRetry={retry} />
        ) : !health.data || !version.data ? (
          <div className="flex flex-col gap-3" role="status" aria-live="polite">
            <span className="sr-only">{t('status.loading')}</span>
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-full" />
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <Badge className="bg-success text-success-foreground" data-testid="api-status">
                {t('status.connected')}
              </Badge>
            </div>
            <dl>
              <Row label={t('version.app')} testId="app-version">
                {version.data.app}
              </Row>
              <Row label={t('version.aacf')} testId="aacf-version">
                {version.data.aacf ?? t('version.unavailable')}
              </Row>
              <Row label={t('status.database')} testId="database-status">
                {t('status.databaseOk')}
              </Row>
              <Row label={t('status.migration')} testId="migration-status">
                <MigrationText migrations={health.data.database.migrations} />
              </Row>
            </dl>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }): React.JSX.Element {
  const { t } = useTranslation();
  const { message, reference } = describeApiError(error, t);
  return (
    <div className="flex flex-col items-start gap-3" role="alert">
      <Badge variant="destructive" data-testid="api-status">
        {t('status.disconnected')}
      </Badge>
      <p className="text-sm text-foreground" data-testid="api-error">
        {message}
      </p>
      {reference ? <p className="font-mono text-xs text-muted-foreground">{reference}</p> : null}
      <Button variant="outline" onClick={onRetry}>
        {t('actions.retry')}
      </Button>
    </div>
  );
}
