// Where a finding of the NT 10/17 validator (E16) is.
import type { Finding } from '@/types/validation';

const POSITION = /([A-Z0-9]{6}) (\d{2}) (\d{2})/;
const ARTICLES = '/articulos';

/** Where "Ir a" takes a finding: the row in the tree with its card (and
 *  the field), a product's tab, or the article. */
export function findingTarget(materialId: string, f: Finding): string | null {
  if (f.entity_type === 'producto') return `/materiales/${materialId}/confunfis/productos`;
  if (f.row_id) {
    const q = new URLSearchParams({ fila: f.row_id });
    const position = POSITION.exec(f.location);
    if (position) q.set('buscar', position[1]);
    if (f.field) q.set('campo', f.field);
    return `/materiales/${materialId}/confunfis?${q.toString()}`;
  }
  if (f.entity_type === 'articulo') return `${ARTICLES}/${f.entity_id}`;
  return null;
}
