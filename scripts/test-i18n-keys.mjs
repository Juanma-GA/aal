// HR15: every key the app asks t() for exists in the Spanish locale
// (src/i18n/locales/es.json), no value is empty, and every sanitized error
// code the backend can answer (error_detail("<code>") in backend/app, the
// Excel file errors, an import job's failure, an attribute's problem) has
// its sentence under errors.<code>; every issue of an Excel import (a cell
// error or warning, app/io_excel) under import.issues.<code>.
//
// Run: node scripts/test-i18n-keys.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripComments, walk } from './lib/sourceScan.mjs';
import { readTextFile } from './lib/textFile.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
let checks = 0;
let failures = 0;
function check(name, ok, detail = '') {
  checks += 1;
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}${detail ? ` -- ${detail}` : ''}`);
  }
}

const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));

function lookup(tree, key) {
  return key.split('.').reduce((node, part) => (node && typeof node === 'object' ? node[part] : undefined), tree);
}

function leaves(tree, prefix = '') {
  return Object.entries(tree).flatMap(([k, v]) => (v && typeof v === 'object' ? leaves(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v]]));
}

// t('a.b') / t("a.b"), the literal keys of the code.
const T_CALL = /\bt\(\s*(['"])([\w.]+)\1/g;
const used = new Set();
for (const file of walk(path.join(ROOT, 'src'), /\.(ts|tsx)$/)) {
  for (const m of stripComments(fs.readFileSync(file, 'utf8')).matchAll(T_CALL)) used.add(m[2]);
}
check('finds the keys the app uses', used.size >= 10, String(used.size));
// A key may name a string or, read with returnObjects, a table.
for (const key of used) check(`es.json has "${key}"`, ['string', 'object'].includes(typeof lookup(es, key)));

for (const [key, value] of leaves(es)) check(`es.json "${key}" is not empty`, typeof value === 'string' && value.trim() !== '');

// The backend's sanitized error codes.
const codes = new Set();
for (const file of walk(path.join(ROOT, 'backend', 'app'), /\.py$/)) {
  for (const m of fs.readFileSync(file, 'utf8').matchAll(/error_detail\(\s*"([a-z_]+)"/g)) codes.add(m[1]);
}
const excelEngine = walk(path.join(ROOT, 'backend', 'app'), /\.py$/).map((f) => fs.readFileSync(f, 'utf8')).join('\n');
for (const m of excelEngine.matchAll(/ExcelFileError\(\s*"([a-z_]+)"/g)) codes.add(m[1]);
for (const m of excelEngine.matchAll(/"failed", "([a-z_]+)"|_conflict\(\s*"([a-z_]+)"/g)) codes.add(m[1] ?? m[2]);
for (const m of excelEngine.matchAll(/return "([a-z_]+)", \{/g)) codes.add(m[1]);
const issues = new Set();
for (const m of excelEngine.matchAll(/(?:CellError|Issue)\(\s*"([a-z_]+)"|warning = \("([a-z_]+)"/g)) issues.add(m[1] ?? m[2]);
check('finds the Excel import issues', issues.size >= 15, [...issues].join(', '));
for (const issue of issues) check(`es.json has import.issues.${issue}`, typeof lookup(es, `import.issues.${issue}`) === 'string');
check('finds the backend error codes', codes.size >= 3, [...codes].join(', '));
for (const code of codes) check(`es.json has errors.${code}`, typeof lookup(es, `errors.${code}`) === 'string');
// The client's own codes (src/services/apiClient.ts).
for (const code of ['network_error', 'http_error', 'unknown', 'ref']) check(`es.json has errors.${code}`, typeof lookup(es, `errors.${code}`) === 'string');

// The catalogue codes the UI shows by name (src/lib/labels.ts): the roles,
// permissions and areas seeded by the migrations and every audit action
// and entity the backend records.
const backendText = walk(path.join(ROOT, 'backend'), /\.py$/)
  .filter((f) => !f.includes(`${path.sep}.venv${path.sep}`) && !f.includes(`${path.sep}tests${path.sep}`))
  .map((f) => fs.readFileSync(f, 'utf8'))
  .join('\n');
const migrations = walk(path.join(ROOT, 'backend', 'alembic', 'versions'), /\.py$/).map((f) => fs.readFileSync(f, 'utf8')).join('\n');
const rolesBlock = migrations.match(/^ROLES = \(([^)]*)\)/m)?.[1] ?? '';
const roles = [...rolesBlock.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
const permissions = [...migrations.matchAll(/^\s+\("([a-z_.]+)", "([a-z_]+)"\),$/gm)].map((m) => ({ code: m[1], area: m[2] }));
const actions = new Set([...backendText.matchAll(/action\s?=\s?"([a-z_]+\.[a-z_.]+)"/g)].map((m) => m[1]));
for (const m of backendText.matchAll(/_member_audit\([^)]*"(material_role\.[a-z_]+)"/g)) actions.add(m[1]);
const entities = new Set([...backendText.matchAll(/entity_type="([a-z_]+)"/g)].map((m) => m[1]));
check('finds the seeded roles', roles.length === 3, roles.join(', '));
check('finds the seeded permissions', permissions.length >= 16, String(permissions.length));
check('finds the audit actions', actions.size >= 15, [...actions].join(', '));
for (const role of roles) check(`es.json roles has ${role}`, typeof es.roles?.[role] === 'string');
for (const { code, area } of permissions) {
  check(`es.json permissions has ${code}`, typeof es.permissions?.[code] === 'string');
  check(`es.json areas has ${area}`, typeof es.areas?.[area] === 'string');
}
for (const action of actions) check(`es.json audit.actions has ${action}`, typeof es.audit?.actions?.[action] === 'string');
for (const entity of entities) check(`es.json audit.entities has ${entity}`, typeof es.audit?.entities?.[entity] === 'string');

// The module states (backend/app/models/module.py) and the phases of the
// catalog seed (backend/app/seeds/module_catalog_seed.yaml), shown by name.
const moduleModel = fs.readFileSync(path.join(ROOT, 'backend', 'app', 'models', 'module.py'), 'utf8');
const statuses = [...(moduleModel.match(/^MODULE_STATUSES = \(([^)]*)\)/m)?.[1] ?? '').matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
const seedText = readTextFile(path.join(ROOT, 'backend', 'app', 'seeds', 'module_catalog_seed.yaml'));
const phases = new Set([...seedText.matchAll(/^\s+fase: '?([0-9a-z]+)'?$/gm)].map((m) => m[1]));
check('finds the module states', statuses.length === 3, statuses.join(', '));
check('finds the phases of the seed', phases.size >= 5, [...phases].join(', '));
for (const status of statuses) check(`es.json modules.status has ${status}`, typeof es.modules?.status?.[status] === 'string');
for (const phase of phases) check(`es.json modules.phase has ${phase}`, typeof es.modules?.phase?.[phase] === 'string');

console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
