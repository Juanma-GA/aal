// E10: the client's real catalog, private/CONF_FUN_V3_0.xlsx (D13: never in
// the repo), imported through the API with the figures of the encargo §1:
// 9 572 rows, 6 786 SNS, 11 categories (10 + 00 General), 39
// subcategories, rows per declared level, CN-001 19, CN-002 18 (+53
// ELEMENTO), CN-003 2, CN-004 3, CN-005 9, CN-006 1 364 PTE rows (1 311
// SNS) and some TBD. It also reports how long the analysis and the
// applying take. Leaves the database as it was (the version and its import
// job are removed, the previous active version is active again).
//
// Without the file it exits 2 (NOT RUN), never 1. Needs uvicorn and Vite
// (BASE_URL), and VERIFY_ADMIN_EMAIL / VERIFY_ADMIN_PASSWORD.
//
//   node scripts/verify-conf-fun-real.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { apiSession, backendPythonOrNotRun, notRun, purgeVerifyData } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const FILE = path.join(ROOT, 'private', 'verify-CONF_FUN_V3_0.xlsx'); // verify-…: the cleanup removes it
const EXPECTED = {
  rows: 9572, sns: 6786, categories: 11, subcategories: 39,
  rows_subconjunto: 3208, rows_conjunto: 2936, rows_subsistema: 1572, rows_subsubsistema: 1326, rows_sistema: 477, rows_elemento: 53,
  cn_001: 19, cn_002: 18, cn_003: 2, cn_004: 3, cn_005: 9,
};
const POLL_MS = 1000;
const MAX_WAIT_MS = 10 * 60 * 1000;

if (!fs.existsSync(FILE)) notRun(`${path.relative(ROOT, FILE)} is not there (the client's file, D13).`);
if (!process.env.VERIFY_ADMIN_EMAIL || !process.env.VERIFY_ADMIN_PASSWORD) notRun('set VERIFY_ADMIN_EMAIL and VERIFY_ADMIN_PASSWORD.');
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const api = await apiSession(BASE_URL, process.env.VERIFY_ADMIN_EMAIL, process.env.VERIFY_ADMIN_PASSWORD);
const login = await fetch(`${BASE_URL}/api/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: process.env.VERIFY_ADMIN_EMAIL, password: process.env.VERIFY_ADMIN_PASSWORD }),
});
const { access_token: token } = await login.json();

let failures = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK' : 'FAIL'}: ${name} = ${actual}${ok ? '' : ` (expected ${expected})`}`);
}

const importJobs = [];
const catalogVersions = [];
try {
  const form = new FormData();
  form.append('file', new Blob([fs.readFileSync(FILE)]), 'verify-CONF_FUN_V3_0.xlsx'); // verify-…: the cleanup removes it
  const started = Date.now();
  const res = await fetch(`${BASE_URL}/api/catalog/import`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (res.status !== 202) throw new Error(`the upload answered ${res.status}: ${await res.text()}`);
  let job = await res.json();
  importJobs.push(job.id);
  while (job.status === 'analyzing') {
    if (Date.now() - started > MAX_WAIT_MS) throw new Error('the analysis did not finish in 10 minutes');
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    job = await api('GET', `/import-jobs/${job.id}`);
  }
  const analysed = Date.now();
  if (job.status !== 'analyzed') throw new Error(`the analysis ended ${job.status}: ${job.error_code}`);
  console.log(`analysis: ${((analysed - started) / 1000).toFixed(1)} s`);
  for (const [key, value] of Object.entries(EXPECTED)) check(key, job.counts[key], value);
  const pte = job.report.warnings.filter((w) => w.code === 'cn_006' && w.params.mark === 'PTE');
  check('CN-006 rows PTE', pte.length, 1364);
  check('CN-006 SNS PTE', new Set(pte.map((w) => w.params.sns)).size, 1311);
  console.log(`CN-006 rows TBD: ${job.report.warnings.filter((w) => w.code === 'cn_006' && w.params.mark === 'TBD').length}`);
  check('errors', job.counts.errors, 0);
  await api('POST', `/import-jobs/${job.id}/apply`);
  console.log(`apply: ${((Date.now() - analysed) / 1000).toFixed(1)} s`);
  const [version] = await api('GET', '/catalog/versions');
  catalogVersions.push(version.id);
  check('the new version is active', version.is_active, true);
} catch (err) {
  failures += 1;
  console.error(err.message);
} finally {
  purgeVerifyData(python, { importJobs, catalogVersions });
}
console.log(failures ? `verify-conf-fun-real: ${failures} FAILED` : 'verify-conf-fun-real: ALL OK');
process.exit(failures ? 1 : 0);
