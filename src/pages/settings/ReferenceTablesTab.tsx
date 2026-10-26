import { useParams } from 'react-router-dom';
import { ArticleFieldsTable } from '@/components/reference/ArticleFieldsTable';
import { ReferenceTablesList } from '@/components/reference/ReferenceTablesList';
import { ReferenceTableView } from '@/components/reference/ReferenceTableView';

const BASE = '/ajustes/tablas-referencia';

/** Ajustes -> Tablas de referencia: the list, or one table to edit. */
export function ReferenceTablesTab(): React.JSX.Element {
  const { code } = useParams();
  return code ? <ReferenceTableView key={code} code={code} base={BASE} /> : <ReferenceTablesList base={BASE} />;
}

/** Ajustes -> Campos del artículo: the admin corrects a definition (E13). */
export function ArticleFieldsTab(): React.JSX.Element {
  return <ArticleFieldsTable tablesBase={BASE} editable />;
}
