// E16: the NT 10/17 validator over the official example of the Anexo XI,
// private/CON_FUN_FIS2_ejemplo.xlsx (D13: never in the repo; 714 rows),
// imported through the API into a temporary CUF with every subcategory of
// the active catalog version (applying it validates the CUF), then
// "Validar ahora" once more, timed:
//   - the figures measured in the plan: CF-002 = 2, CF-007 = 6, CF-008 = 46,
//     CF-012 = 52, CF-014 = 52, CF-015 = 21 (each other rule's count is
//     printed, not checked);
//   - a validation of the 714 rows in under 3 s (VALIDATION_REAL_MAX_S).
// Leaves the database as it was: the temporary CUF (with its validations)
// and its import job are removed, and the articles (the provisional ones
// the import created) put back as they were (purge_verify_data.py
// --save-articles / --restore-articles).
//
// Without the file it exits 2 (NOT RUN), never 1. Needs uvicorn and Vite
// (BASE_URL), and VERIFY_ADMIN_EMAIL / VERIFY_ADMIN_PASSWORD. Not in the CI.
//
//   node scripts/verify-validation-real.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { apiSession, backendPythonOrNotRun, notRun, purgeVerifyData, runBackendScript } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const FILE = path.join(ROOT, 'private', 'CON_FUN_FIS2_ejemplo.xlsx');
const EXPECTED = { 'CF-002': 2, 'CF-007': 6, 'CF-008': 46, 'CF-012': 52, 'CF-014': 52, 'CF-015': 21 };
const MAX_SECONDS = Number(process.env.VALIDATION_REAL_MAX_S || 3);
const POLL_MS = 1000;
const MAX_WAIT_MS = 10 * 60 * 1000;
const NAME = `[verify] CUF del ejemplo real (validación) ${Date.now()}`;

if (!fs.existsSync(FILE)) notRun(`${path.relative(ROOT, FILE)} is not there (the official example, D13).`);
if (!process.env.VERIFY_ADMIN_EMAIL || !process.env.VERIFY_ADMIN_PASSWORD) notRun('set VERIFY_ADMIN_EMAIL and VERIFY_ADMIN_PASSWORD.');
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const api = await apiSession(BASE_URL, process.env.VERIFY_ADMIN_EMAIL, process.env.VERIFY_ADMIN_PASSWORD);
const token = (await (await fetch(`${BASE_URL}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: process.env.VERIFY_ADMIN_EMAIL, password: process.env.VERIFY_ADMIN_PASSWORD }),
})).json()).access_token;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'verify-validation-real-'));
const ARTICLES = path.join(tmp, 'articles.json');
if (runBackendScript(python, 'save the articles', [path.join('scripts', 'purge_verify_data.py'), '--save-articles', '--snapshot', ARTICLES]) !== 0) {
  fs.rmSync(tmp, { recursive: true, force: true });
  notRun('could not save the articles.');
}

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK' : 'FAIL'}: ${name}${detail ? ` -- ${detail}` : ''}`);
}

const importJobs = [];
try {
  const material = await api('POST', '/materials', { name: NAME, description: 'Creado y borrado por verify-validation-real.' });
  const [active] = (await api('GET', '/catalog/versions')).filter((v) => v.is_active);
  const categories = await api('GET', `/catalog/versions/${active.id}/categories`);
  const codes = categories.categories.flatMap((c) => c.subcategories.map((s) => s.code));
  const cuf = await api('GET', `/materials/${material.id}/cuf`);
  await api('PUT', `/materials/${material.id}/subcategories`, { version: cuf.version, codes });
  console.log(`temporary CUF with the ${codes.length} subcategories of catalog version ${active.number}`);

  const form = new FormData();
  form.append('file', new Blob([fs.readFileSync(FILE)]), 'CON_FUN_FIS2_ejemplo.xlsx');
  const started = Date.now();
  const upload = await fetch(`${BASE_URL}/api/materials/${material.id}/confunfis/import?mode=merge`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (upload.status !== 202) throw new Error(`the upload answered ${upload.status}: ${await upload.text()}`);
  let job = await upload.json();
  importJobs.push(job.id);
  while (job.status === 'analyzing') {
    if (Date.now() - started > MAX_WAIT_MS) throw new Error('the analysis did not finish in 10 minutes');
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    job = await api('GET', `/import-jobs/${job.id}`);
  }
  if (job.status !== 'analyzed') throw new Error(`the analysis ended ${job.status}: ${job.error_code}`);
  console.log(`analysis: ${((Date.now() - started) / 1000).toFixed(1)} s; what the result would have: ${JSON.stringify(job.report.result.observations)}`);
  const applied = await fetch(`${BASE_URL}/api/materials/${material.id}/confunfis/import/${job.id}/apply`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm_cuf: true }),
  });
  check('applied', applied.ok, `${applied.status}`);
  const after = await api('GET', `/materials/${material.id}/validation`);
  check('applying the book validated the CUF', after.trigger === 'import', after.trigger ?? 'not validated');

  const clock = Date.now();
  const report = await api('POST', `/materials/${material.id}/validation`);
  const wall = (Date.now() - clock) / 1000;
  const rows = (await api('GET', `/materials/${material.id}/confunfis/summary`)).rows;
  check(`${rows} rows validated in under ${MAX_SECONDS} s`, report.seconds < MAX_SECONDS, `${report.seconds} s in the server, ${wall.toFixed(1)} s the request`);
  const counts = Object.fromEntries(report.by_rule.map((r) => [r.code, r.findings]));
  console.log(`by rule: ${report.by_rule.map((r) => `${r.code} ${r.findings} (${r.severity})`).join(' · ')}`);
  for (const [code, n] of Object.entries(EXPECTED)) check(`${code} = ${n}`, (counts[code] ?? 0) === n, `${counts[code] ?? 0}`);
  console.log(`state ${report.state}: ${report.blocking} blocking, ${report.warnings} warnings`);
} catch (err) {
  failures += 1;
  console.error(err.message);
} finally {
  purgeVerifyData(python, { materials: [NAME], importJobs });
  runBackendScript(python, 'cleanup', [path.join('scripts', 'purge_verify_data.py'), '--restore-articles', '--snapshot', ARTICLES]);
  fs.rmSync(tmp, { recursive: true, force: true });
}
console.log(failures ? `verify-validation-real: ${failures} FAILED` : 'verify-validation-real: ALL OK');
process.exit(failures ? 1 : 0);
