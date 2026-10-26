// E15: the official example of the Anexo XI, private/CON_FUN_FIS2_ejemplo.xlsx
// (D13: never in the repo; 714 rows in CON_FUN_FIS, no TABLA DE PARTES,
// auxiliary sheets), imported through the API into a temporary CUF with
// every subcategory of the active catalog version, and its round trip:
//   - the analysis: rows, rejected, observations, provisional articles, the
//     sheets ignored, and how long it takes; the CUF of the file is other
//     than the temporary one, so it is confirmed;
//   - applied, then exported (Anexo XI): the same values as the file sheet
//     by sheet, the CUF's columns aside (backend/scripts/compare_books.py);
//   - the export imported again (Fusionar): 0 changes.
// Leaves the database as it was: the temporary CUF and its import jobs are
// removed, and the articles (the provisional ones the import created) put
// back as they were (purge_verify_data.py --save-articles / --restore-articles).
//
// Without the file it exits 2 (NOT RUN), never 1. Needs uvicorn and Vite
// (BASE_URL), and VERIFY_ADMIN_EMAIL / VERIFY_ADMIN_PASSWORD. Not in the CI.
// CONFUNFIS_REAL_ROWS: the rows expected, if another example (default 714).
//
//   node scripts/verify-confunfis-real.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { BACKEND_DIR, pythonEnv } from './lib/backendPython.mjs';
import { apiSession, backendPythonOrNotRun, notRun, purgeVerifyData, runBackendScript } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const FILE = path.join(ROOT, 'private', 'CON_FUN_FIS2_ejemplo.xlsx');
const EXPECTED_ROWS = Number(process.env.CONFUNFIS_REAL_ROWS || 714);
const POLL_MS = 1000;
const MAX_WAIT_MS = 10 * 60 * 1000;
const NAME = `[verify] CUF del ejemplo real ${Date.now()}`;

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
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'verify-confunfis-real-'));
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

async function analysed(materialId, data, fileName) {
  const form = new FormData();
  form.append('file', new Blob([data]), fileName);
  const started = Date.now();
  const res = await fetch(`${BASE_URL}/api/materials/${materialId}/confunfis/import?mode=merge`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (res.status !== 202) throw new Error(`the upload answered ${res.status}: ${await res.text()}`);
  let job = await res.json();
  importJobs.push(job.id);
  while (job.status === 'analyzing') {
    if (Date.now() - started > MAX_WAIT_MS) throw new Error('the analysis did not finish in 10 minutes');
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    job = await api('GET', `/import-jobs/${job.id}`);
  }
  if (job.status !== 'analyzed') throw new Error(`the analysis ended ${job.status}: ${job.error_code}`);
  return { job, seconds: (Date.now() - started) / 1000 };
}

async function download(materialId) {
  const res = await fetch(`${BASE_URL}/api/materials/${materialId}/confunfis/export?kind=anexo`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`the export answered ${res.status}`);
  return Buffer.from(await res.arrayBuffer());
}

const importJobs = [];
try {
  const material = await api('POST', '/materials', { name: NAME, description: 'Creado y borrado por verify-confunfis-real.' });
  const [active] = (await api('GET', '/catalog/versions')).filter((v) => v.is_active);
  const categories = await api('GET', `/catalog/versions/${active.id}/categories`);
  const codes = categories.categories.flatMap((c) => c.subcategories.map((s) => s.code));
  const cuf = await api('GET', `/materials/${material.id}/cuf`);
  await api('PUT', `/materials/${material.id}/subcategories`, { version: cuf.version, codes });
  console.log(`temporary CUF with the ${codes.length} subcategories of catalog version ${active.number}`);

  const { job, seconds } = await analysed(material.id, fs.readFileSync(FILE), 'CON_FUN_FIS2_ejemplo.xlsx');
  const fun = job.report.sheets.CON_FUN_FIS;
  console.log(`analysis: ${seconds.toFixed(1)} s`);
  console.log(`sheets ignored: ${job.report.ignored_sheets.join(', ') || 'none'}; read: ${Object.keys(job.report.sheets).join(', ')}`);
  console.log(`CON_FUN_FIS: ${fun.new.length} new, ${fun.rejected.length} rejected`);
  for (const r of fun.rejected.slice(0, 10)) console.log(`  rejected row ${r.row}: ${r.issues.map((i) => i.code).join(', ')}`);
  console.log(`observations: ${JSON.stringify(job.report.result.observations)}`);
  console.log(`provisional articles: ${job.report.result.provisional_articles.length}; new P/N: ${job.report.result.new_references.length}`);
  check(`${EXPECTED_ROWS} rows read`, fun.new.length + fun.rejected.length === EXPECTED_ROWS, `${fun.new.length + fun.rejected.length}`);
  check('no errors in the file', job.counts.errors === 0);
  check('the file is the CUF of another material: to be confirmed', job.report.cuf.differs === true);

  const applyStart = Date.now();
  const res = await fetch(`${BASE_URL}/api/materials/${material.id}/confunfis/import/${job.id}/apply`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm_cuf: true }),
  });
  check('applied', res.ok, `${res.status}`);
  console.log(`apply: ${((Date.now() - applyStart) / 1000).toFixed(1)} s`);

  const exported = await download(material.id);
  const mine = path.join(tmp, 'export.xlsx');
  fs.writeFileSync(mine, exported);
  const compared = spawnSync(python, [path.join('scripts', 'compare_books.py'), FILE, mine, '--skip', 'CON_FUN_FIS=4', '--skip', 'TABLA PRODUCTOS FUNCIONALES=3', '--min-row', '3'], { cwd: BACKEND_DIR, env: pythonEnv(), encoding: 'utf8' });
  const sheets = JSON.parse(compared.stdout || '{}');
  for (const name of ['CON_FUN_FIS', 'TABLA PRODUCTOS FUNCIONALES']) {
    const s = sheets[name];
    if (!s || s.missing) {
      console.log(`${name}: not in the example`);
      continue;
    }
    check(`${name}: the export has the file's rows (the CUF's columns and the headers aside)`, s.equal, s.equal ? '' : `${s.only_first} rows only in the file · ${s.only_second} only in the export`);
  }
  const again = await analysed(material.id, exported, 'export.xlsx');
  const c = again.job.counts;
  check('the export imported again (Fusionar): 0 changes', c.new === 0 && c.modified === 0 && c.removed === 0, JSON.stringify({ new: c.new, modified: c.modified, removed: c.removed }));
  console.log(`analysis of the export: ${again.seconds.toFixed(1)} s`);
} catch (err) {
  failures += 1;
  console.error(err.message);
} finally {
  purgeVerifyData(python, { materials: [NAME], importJobs });
  runBackendScript(python, 'cleanup', [path.join('scripts', 'purge_verify_data.py'), '--restore-articles', '--snapshot', ARTICLES]);
  fs.rmSync(tmp, { recursive: true, force: true });
}
console.log(failures ? `verify-confunfis-real: ${failures} FAILED` : 'verify-confunfis-real: ALL OK');
process.exit(failures ? 1 : 0);
