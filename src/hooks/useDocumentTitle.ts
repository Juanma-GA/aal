import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/** The browser tab's title for a page: "<page> · AAL — ..." (the app's
 *  name alone when the page has none yet). */
export function useDocumentTitle(page: string | null | undefined): void {
  const { t } = useTranslation();
  useEffect(() => {
    document.title = page ? t('nav.pageTitle', { page, app: t('app.title') }) : t('app.title');
  }, [page, t]);
}
