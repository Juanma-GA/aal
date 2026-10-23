// The SNS level/parent rule of the frontend (src/lib/sns.ts) is the
// backend's (backend/app/services/catalog.py, its truth table in
// backend/tests/unit/test_catalog_rules.py).
//
// Run: node scripts/test-sns.mjs
import { ancestors, derivedParent } from '../src/lib/sns.ts';

let failures = 0;
function check(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);
  }
}
const table = [
  ['000000', null], ['A20000', null], ['A21000', 'A20000'], ['A22100', 'A22000'], ['A21030', 'A21000'],
  ['A21326', 'A21320'], ['ZLC150', 'ZLC100'], ['L4121C', 'L41210'], ['B34510', 'B34500'], ['AB0C00', 'AB0000'],
];
for (const [sns, parent] of table) check(`parent of ${sns}`, derivedParent(sns), parent);
check('ancestors of A21031', ancestors('A21031'), ['A20000', 'A21000', 'A21030']);
check('ancestors of a system', ancestors('B00000'), []);
console.log(`${table.length + 2 - failures}/${table.length + 2} checks passed`);
process.exit(failures ? 1 : 0);
