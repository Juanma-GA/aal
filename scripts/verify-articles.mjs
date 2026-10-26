// E12: the article master, in a real browser, with demo/FICHERO_CARGA_DEMO.xlsx.
//   1. The admin imports the demo from Artículos -> Importar -> Fichero Carga
//      and sees the report: 45 articles, AR-001/002/003/006/007 one each.
//   2. The development analyst searches the BIELA DM-6, opens its card from
//      its row, sees AR-006 and the help of field 53 (mantenimiento preventivo).
//   3. Turns its life control on with a D114 code and a quantity: AR-006 goes.
//   4. In "Editar en rejilla" applies "Escalón 4 = S" to two articles and
//      saves them.
//   5. Exports the Fichero Carga (after its summary of AR warnings).
// Leaves the database as it was: every article is saved before and put back
// after, an article the check created is removed, and so is its import job
// (backend/scripts/purge_verify_data.py); only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py and the data of seed_dev_data.py.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, or without the servers, it says so and exits 2 (NOT RUN).
//
//   node scripts/verify-articles.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';
import { backendPythonOrNotRun, notRun, purgeVerifyData, runBackendScript } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const ADMIN_EMAIL = process.env.VERIFY_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.VERIFY_ADMIN_PASSWORD;
const ANALYST_EMAIL = process.env.VERIFY_ANALISTA_EMAIL || 'analista.dev@aal-dev.es';
const ANALYST_PASSWORD = process.env.DEV_ANALISTA_PASSWORD;
const DEMO = path.join(ROOT, 'demo', 'FICHERO_CARGA_DEMO.xlsx');
const ROD = 'BIELA DM-6';
// Two with escalón 4 = N in the demo.
const GRID_ROWS = ['ARMARIO BASTIDOR 10U', 'ARMARIO BASTIDOR 12U'];
const SNAPSHOT = shot(`verify-articles-${Date.now()}.json`);
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
// demo/LEEME_DATOS_DEMO.md §4 and backend/tests/integration/test_articles.py.
const AR = { ar_001: 1, ar_002: 1, ar_003: 1, ar_004: 0, ar_005: 0, ar_006: 1, ar_007: 1 };

function assert(cond, msg) {
  if (!cond) throw new Error('ASSERTION FAILED: ' + msg);
  console.log('OK:', msg);
}

if (!ADMIN_EMAIL || !ADMIN_PASSWORD || !ANALYST_PASSWORD) {
  notRun('set VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD and DEV_ANALISTA_PASSWORD (create_admin_user.py, seed_dev_data.py).');
}
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const purge = path.join('scripts', 'purge_verify_data.py');
if (runBackendScript(python, 'save the articles', [purge, '--save-articles', '--snapshot', SNAPSHOT]) !== 0) notRun('could not save the articles.');
const importJobs = [];

async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
  await page.getByTestId('user-menu').waitFor();
}

async function signOut(page) {
  await page.getByTestId('user-menu').click();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/logout')), page.getByTestId('sign-out').click()]);
  await page.waitForURL('**/login');
}

async function choose(page, trigger, name) {
  await trigger.click();
  await page.getByRole('option', { name, exact: true }).click();
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. The admin imports the demo ──────────────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto(`${BASE_URL}/articulos`);
  await page.getByTestId('articles-page').waitFor();
  await page.getByTestId('articles-import').click();
  await page.getByTestId('articles-import-fichero_carga').click();
  await page.getByTestId('import-file').setInputFiles({ name: 'FICHERO_CARGA_DEMO.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: fs.readFileSync(DEMO) });
  const analysed = page.waitForResponse(async (r) => r.url().includes('/api/import-jobs/') && r.request().method() === 'GET' && (await r.json()).status === 'analyzed');
  const [started] = await Promise.all([page.waitForResponse((r) => r.url().includes('/api/articles/import') && r.request().method() === 'POST'), page.getByTestId('import-analyze').click()]);
  importJobs.push((await started.json()).id);
  const job = await (await analysed).json();
  const c = job.counts;
  assert(c.rows === 45 && c.new + c.unchanged + c.modified === 45 && c.rejected === 0 && c.errors === 0, `45 articles in the report (${c.new} new, ${c.unchanged} unchanged)`);
  for (const [key, value] of Object.entries(AR)) assert(c[key] === value, `the report counts ${key.replace('ar_', 'AR-')} = ${value}`);
  await page.getByTestId('import-tab-ar').click();
  assert((await page.getByTestId('import-ar-AR-006').textContent()).includes(ROD), 'the AR tab lists the BIELA DM-6 under AR-006');
  await page.screenshot({ path: shot('verify-articles-1-report.png') });
  const [applied] = await Promise.all([page.waitForResponse((r) => r.url().includes('/apply')), page.getByTestId('import-apply').click()]);
  assert(applied.ok(), 'the import is applied');
  await page.getByTestId('import-done').waitFor();
  await page.keyboard.press('Escape');
  await signOut(page);

  // ── 2. The analyst opens the BIELA ─────────────────────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.goto(`${BASE_URL}/articulos`);
  await page.getByTestId('article-search').fill('biela');
  const row = page.getByTestId(`article-row-${ROD}`);
  await row.getByTestId('row-badge-AR-006').waitFor();
  assert(true, 'its row has the AR-006 badge');
  await row.locator('td').nth(1).click();
  await page.getByTestId('article-page').waitFor();
  await page.getByTestId('finding-AR-006').waitFor();
  assert(true, 'its card shows AR-006');
  await page.getByTestId('help-snMtPreArt').click();
  const help = page.getByTestId('help-content-snMtPreArt');
  await help.waitFor();
  const helpText = await help.textContent();
  assert(helpText.includes('MAR06 53') && helpText.includes('MANT. PREVENTIVO') && helpText.includes(es.articles.help.definicion), 'the help of field 53, from the MAR06 guide');
  await page.screenshot({ path: shot('verify-articles-2-help.png') });
  await page.keyboard.press('Escape');

  // ── 3. Life control on: AR-006 goes ────────────────────────────────────
  await page.getByTestId('finding-go-AR-006').click();
  await choose(page, page.getByTestId('field-snCtrlVidaArt'), `S ${es.articles.yesNo.S}`);
  await page.getByTestId('add-life-control').click();
  await page.getByTestId('field-cdUniVidaA').click();
  await page.getByRole('option').filter({ hasText: /^01\b/ }).first().click();
  await page.getByTestId('field-caVidaArt').fill('500');
  const [saved] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/articles/') && r.request().method() === 'PATCH'),
    page.getByTestId('article-save').click(),
  ]);
  assert(saved.ok(), 'the change is saved');
  await page.getByTestId('article-no-findings').waitFor();
  assert((await page.getByTestId('finding-AR-006').count()) === 0, 'AR-006 is gone');
  await page.screenshot({ path: shot('verify-articles-3-saved.png'), fullPage: true });

  // ── 4. The grid: Escalón 4 = S on two articles ─────────────────────────
  await page.goto(`${BASE_URL}/articulos`);
  await page.getByTestId('articles-grid-toggle').click();
  await page.getByTestId('article-grid').waitFor();
  for (const name of GRID_ROWS) await page.getByTestId(`grid-select-${name}`).click();
  await choose(page, page.getByTestId('bulk-field'), 'Manto. individual escalón 4º (S/N)');
  await choose(page, page.getByTestId('bulk-value'), `S ${es.articles.yesNo.S}`);
  await page.getByTestId('bulk-apply').click();
  const [batch] = await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/articles/batch')), page.getByTestId('grid-save').click()]);
  const results = await batch.json();
  assert(results.length >= 2 && results.every((r) => r.ok), `the grid saves its rows (${results.length})`);
  for (const name of GRID_ROWS) {
    const saved4 = results.find((r) => r.article?.nombre === name);
    assert(saved4?.article.fields.snMtN4Art === 'S', `${name}: escalón 4 = S`);
  }
  await page.screenshot({ path: shot('verify-articles-4-grid.png') });

  // ── 5. Export the Fichero Carga ────────────────────────────────────────
  await page.getByTestId('articles-grid-toggle').click();
  await page.getByTestId('articles-export').click();
  await page.getByTestId('articles-export-fichero_carga').click();
  const summary = page.getByTestId('article-export-summary');
  await summary.waitFor();
  assert((await summary.textContent()).includes('45'), 'the export says how many articles go');
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('article-export-run').click()]);
  const file = shot(download.suggestedFilename());
  await download.saveAs(file);
  assert(/^FICHERO_CARGA_\d{8}\.xlsx$/.test(download.suggestedFilename()) && fs.statSync(file).size > 0, `the Fichero Carga is downloaded (${download.suggestedFilename()})`);
  fs.rmSync(file, { force: true });

  const unexpected = consoleErrors.filter((e) => !/\b401\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-articles: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
  await browser.contexts()[0]?.pages()[0]?.screenshot({ path: shot('verify-articles-error.png') }).catch(() => undefined);
} finally {
  await browser.close();
  runBackendScript(python, 'cleanup', [purge, '--restore-articles', '--snapshot', SNAPSHOT]);
  purgeVerifyData(python, { importJobs });
}
process.exit(failed ? 1 : 0);
