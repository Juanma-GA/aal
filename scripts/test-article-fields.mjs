// The check of an article's cell (src/lib/articleFields.ts, E12): S/N,
// numbers with their digits and decimals, lengths and table codes, as the
// server checks them (app/services/article_fields.py).
// Run: node scripts/test-article-fields.mjs
import { cellProblem, cellValue } from '../src/lib/articleFields.ts';

let failures = 0;
let checks = 0;
function check(name, ok) {
  checks += 1;
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}`);
  }
}
const field = (patch) => ({ prisma_code: 'x', name: 'x', importance: 'Obligatorio', guide_field: '1', data_type: 'Carácter', length: 2, decimals: null, related_to: null, supplied_by_contractor: 'S', reference_table_code: null, reference_table_name: null, header: null, allowed_values: null, help: null, ...patch });
const yesNo = field({ length: 1, allowed_values: ['S', 'N'], reference_table_code: 'D114' });
const weight = field({ data_type: 'Numérico', length: 7, decimals: 2 });
const unit = field({ reference_table_code: 'D112' });
const codes = new Set(['KG', 'CM']);

check('S is fine, lower case too', cellProblem(yesNo, 's') === null);
check('X is not S/N', cellProblem(yesNo, 'X')?.code === 'not_a_choice');
check('a S/N field is not checked against its related table', cellProblem(yesNo, 'S', new Set()) === null);
check('empty is fine (AR-001 says if it is required)', cellProblem(weight, '') === null);
check('99999.99 fits 7 digits, 2 decimals', cellProblem(weight, '99999.99') === null);
check('a decimal comma', cellProblem(weight, '12,5') === null && cellValue(weight, '12,5') === '12.5');
check('three decimals', cellProblem(weight, '1.234')?.code === 'too_many_decimals');
check('trailing zeros are no decimals', cellProblem(weight, '1.500') === null);
check('100000 has too many digits', cellProblem(weight, '100000')?.code === 'too_many_digits');
check('letters are no number', cellProblem(weight, '12a')?.code === 'not_decimal');
check('a code of the table', cellProblem(unit, 'kg', codes) === null && cellValue(unit, 'kg') === 'KG');
check('a code not in the table', cellProblem(unit, 'ZZ', codes)?.code === 'not_in_table');
check('the stored code stays valid', cellProblem(unit, 'XX', codes, 'XX') === null);
check('too long', cellProblem(unit, 'KGS', codes)?.code === 'too_long');
console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
