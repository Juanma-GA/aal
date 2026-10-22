// Reference tables and article fields (E03). The same views live in
// Ajustes for an admin (src/pages/settings/ReferenceTablesTab.tsx) and here,
// outside Ajustes, for every signed-in user, who reads them without editing.
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { ArticleFieldsTable } from '@/components/reference/ArticleFieldsTable';
import { ReferenceTablesList } from '@/components/reference/ReferenceTablesList';
import { ReferenceTableView } from '@/components/reference/ReferenceTableView';

export const REFERENCE_TABLES_PATH = '/tablas-referencia';
export const ARTICLE_FIELDS_PATH = '/campos-articulo';

export function ReferenceTablesPage(): React.JSX.Element {
  const { t } = useTranslation();
  const { code } = useParams();
  const crumbs = code ? [{ label: t('reference.title'), to: REFERENCE_TABLES_PATH }, { label: code }] : [{ label: t('reference.title') }];
  return (
    <div className="flex flex-col gap-6">
      <PageHeader crumbs={crumbs} title={t('reference.title')} />
      {code ? <ReferenceTableView key={code} code={code} base={REFERENCE_TABLES_PATH} /> : <ReferenceTablesList base={REFERENCE_TABLES_PATH} />}
    </div>
  );
}

export function ArticleFieldsPage(): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-6">
      <PageHeader crumbs={[{ label: t('articleFields.title') }]} title={t('articleFields.title')} />
      <ArticleFieldsTable tablesBase={REFERENCE_TABLES_PATH} />
    </div>
  );
}
