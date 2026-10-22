// HR21: src/lib/humanize.ts turns machine tokens into readable text.
// Run: node scripts/test-humanize.mjs
import { humanize } from '../src/lib/humanize.ts';

const cases = [
  ['database_unavailable', 'Database unavailable'],
  ['en-revision', 'En revision'],
  ['materialSubcategory', 'Material subcategory'],
  ['SNS_code', 'SNS code'],
  ['NOC', 'NOC'],
  ['borrador', 'Borrador'],
  ['  dos__guiones--y  espacios ', 'Dos guiones y espacios'],
  ['status.up_to_date', 'Status up to date'],
  ['', ''],
  ['A', 'A'],
];
let failures = 0;
for (const [input, expected] of cases) {
  const got = humanize(input);
  if (got !== expected) {
    failures += 1;
    console.error(`FAIL humanize(${JSON.stringify(input)}) = ${JSON.stringify(got)}, expected ${JSON.stringify(expected)}`);
  }
}
console.log(`${cases.length - failures}/${cases.length} checks passed`);
process.exit(failures ? 1 : 0);
