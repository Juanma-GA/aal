// HR15: every key the app asks t() for exists in the Spanish locale
// (src/i18n/locales/es.json), no value is empty, and every sanitized error
// code the backend can answer (error_detail("<code>") in backend/app) has
// its sentence under errors.<code>.
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
for (const key of used) check(`es.json has "${key}"`, typeof lookup(es, key) === 'string');

for (const [key, value] of leaves(es)) check(`es.json "${key}" is not empty`, typeof value === 'string' && value.trim() !== '');

// The backend's sanitized error codes.
const codes = new Set();
for (const file of walk(path.join(ROOT, 'backend', 'app'), /\.py$/)) {
  for (const m of fs.readFileSync(file, 'utf8').matchAll(/error_detail\(\s*"([a-z_]+)"/g)) codes.add(m[1]);
}
check('finds the backend error codes', codes.size >= 3, [...codes].join(', '));
for (const code of codes) check(`es.json has errors.${code}`, typeof lookup(es, `errors.${code}`) === 'string');
// The client's own codes (src/services/apiClient.ts).
for (const code of ['network_error', 'http_error', 'unknown', 'ref']) check(`es.json has errors.${code}`, typeof lookup(es, `errors.${code}`) === 'string');

console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
