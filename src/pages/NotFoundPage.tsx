import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

/** 404: a page that does not exist, or a material the user has no access
 *  to (the server answers both the same: nothing tells which). */
export function NotFoundPage({ kind = 'page' }: { kind?: 'page' | 'material' | 'module' }): React.JSX.Element {
  const { t } = useTranslation();
  useDocumentTitle(t('notFound.title'));
  return (
    <Card data-testid="not-found">
      <CardHeader>
        <CardTitle className="text-xl">{t('notFound.title')}</CardTitle>
        <CardDescription>{t(`notFound.${kind}`)}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild variant="outline">
          <Link to="/">{t('notFound.home')}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
