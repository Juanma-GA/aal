// E10: the normalized functional configuration, in a real browser.
//   1. The admin imports demo/CONF_FUN_DEMO.xlsx from "Importar nueva
//      versión", checks the report (101 rows, 68 SNS, the CN-001..CN-006
//      counts) and applies it.
//   2. Plataformas terrestres -> Vehículos de ruedas: the tree opens down to
//      A21031, whose card shows its extra name.
//   3. Search A27010; A21030 appears in both wheeled and tracked vehicles.
//   4. "Avisos de la versión" shows each CN with its count.
//   5. (E12) A copy with A22140's 06-01 description changed (PTE -> TBD) is
//      imported: CN-007 = 1, and the report and "Comparar" show A22140's rows
//      side by side by subcategory, its description "Varía por subcategoría".
//      The first version is deleted from "Versiones" (the active one cannot be).
//   6. The development analyst sees the catalog but not "Importar".
// Leaves the database as it was: the imported version and its import job
// are removed and the version that was active before is active again
// (backend/scripts/purge_verify_data.py); only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py and the data of seed_dev_data.py.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, or without the servers, it says so and exits 2 (NOT RUN).
//
//   node scripts/verify-conf-fun.mjs
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
const DEMO = path.join(ROOT, 'demo', 'CONF_FUN_DEMO.xlsx');
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
// The NT rules applied to the demo (see backend/tests/integration/test_catalog.py).
const EXPECTED = { rows: 101, sns: 68, categories: 4, subcategories: 5, cn_001: 2, cn_002: 2, cn_003: 2, cn_004: 1, cn_005: 1, cn_006: 7, cn_007: 0 };
// The row of A22140 in 06-01 (its 06-02 row is row 61).
const A22140_0601 = 'H14';

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
const importJobs = [];
const catalogVersions = [];

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

/** Imports a CONF_FUN file from "Importar nueva versión" (named verify-…:
 *  the cleanup only removes versions a check imported); the analysis and
 *  the response of the list once applied. */
async function importVersion(page, name, buffer, check) {
  await page.getByTestId('catalog-import').click();
  await page.getByTestId('import-file').setInputFiles({ name, mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer });
  const analysed = page.waitForResponse(async (r) => r.url().includes('/api/import-jobs/') && r.request().method() === 'GET' && (await r.json()).status === 'analyzed');
  const [started] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/catalog/import') && r.request().method() === 'POST'),
    page.getByTestId('import-analyze').click(),
  ]);
  importJobs.push((await started.json()).id);
  const job = await (await analysed).json();
  await page.getByTestId('import-report').waitFor();
  await check(job);
  // Applying refreshes the list of versions: the new one is the first.
  const listed = page.waitForResponse((r) => r.url().endsWith('/api/catalog/versions') && r.ok());
  const [applied] = await Promise.all([page.waitForResponse((r) => r.url().includes('/apply')), page.getByTestId('import-apply').click()]);
  assert(applied.ok(), `${name} is applied`);
  const newest = (await (await listed).json())[0];
  await page.getByTestId('import-done').waitFor();
  await page.keyboard.press('Escape');
  catalogVersions.push(newest.id);
  return newest;
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. Import the demo catalog ─────────────────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto(`${BASE_URL}/configuracion-funcional`);
  await page.getByTestId('catalog-page').waitFor();
  const newest = await importVersion(page, 'verify-CONF_FUN_DEMO.xlsx', fs.readFileSync(DEMO), async (job) => {
    for (const [key, value] of Object.entries(EXPECTED)) assert(job.counts[key] === value, `the report counts ${key} = ${value}`);
    assert(job.counts.new + job.counts.modified + job.counts.unchanged === 68 && job.counts.errors === 0, 'the 68 SNS, no errors');
    assert((await page.getByTestId('import-count-errors').textContent()) === '0', 'the wizard shows no errors');
    await page.getByTestId('import-tab-warnings').click();
    const warningsText = await page.getByTestId('import-warnings').textContent();
    assert(warningsText.includes('A21031') && warningsText.includes('E11000'), 'the warnings tab lists the CN warnings');
    await page.screenshot({ path: shot('verify-conf-fun-1-report.png') });
  });
  assert(newest.is_active && newest.counts.sns === 68, `version ${newest.number} is the active one`);

  // ── 2. Wheeled vehicles -> A21031 ──────────────────────────────────────
  const land = page.getByTestId('catalog-categories');
  assert((await land.textContent()).includes('PLATAFORMAS TERRESTRES'), 'the categories list Plataformas terrestres');
  await page.getByTestId('subcategory-0601').click();
  await page.getByTestId('tree-node-A20000').waitFor();
  for (const sns of ['A20000', 'A21000', 'A21030']) {
    await page.getByTestId(`tree-toggle-${sns}`).click();
  }
  await page.getByTestId('tree-node-A21031').getByRole('button', { name: /SEGMENTOS/ }).click();
  await page.getByTestId('sns-card').filter({ hasText: 'A21031' }).waitFor();
  const extra = await page.getByTestId('sns-extra-names').textContent();
  assert(extra.includes('JUEGO DE SEGMENTOS') && extra.includes(es.catalog.origins.cn001), 'the card of A21031 shows its extra name');
  assert((await page.getByTestId('sns-card').textContent()).includes(es.catalog.levels.SUBCONJUNTO), 'with its level, humanized');
  await page.screenshot({ path: shot('verify-conf-fun-2-tree.png'), fullPage: true });

  // ── 3. Search ──────────────────────────────────────────────────────────
  await page.getByTestId('catalog-search').fill('A27010');
  await page.getByTestId('search-hit-A27010').waitFor();
  assert(true, 'the search finds A27010');
  await page.getByTestId('catalog-search').fill('A21030');
  const pistons = page.getByTestId('search-hit-A21030');
  await pistons.waitFor();
  assert((await pistons.textContent()).includes('0601, 0602'), 'A21030 is in wheeled and tracked vehicles');
  await pistons.click();
  await page.getByTestId('sns-card').filter({ hasText: 'A21030' }).waitFor();
  const where = await page.getByTestId('sns-appearances').textContent();
  assert(where.includes('VEHÍCULOS DE RUEDAS') && where.includes('VEHÍCULOS DE CADENAS'), 'its card lists both subcategories');

  // ── 4. Warnings of the version ─────────────────────────────────────────
  await page.getByTestId('catalog-tab-avisos').click();
  await page.getByTestId('catalog-warnings').waitFor();
  for (const code of ['cn_001', 'cn_002', 'cn_003', 'cn_004', 'cn_005', 'cn_006', 'cn_007']) {
    assert((await page.getByTestId(`warnings-count-${code}`).textContent()) === String(EXPECTED[code]), `"Avisos de la versión": ${code} = ${EXPECTED[code]}`);
  }
  await page.screenshot({ path: shot('verify-conf-fun-3-warnings.png'), fullPage: true });

  // ── 5. One subcategory's row changed; a version deleted (E12) ──────────
  const edited = shot('verify-conf-fun-A22140.xlsx');
  assert(runBackendScript(python, 'edit', [path.join('scripts', 'verify_edit_xlsx.py'), DEMO, edited, 'CONF_FUN', `${A22140_0601}=TBD`]) === 0, 'A22140 06-01 edited with openpyxl');
  const second = await importVersion(page, 'verify-CONF_FUN_A22140.xlsx', fs.readFileSync(edited), async (job) => {
    assert(job.counts.cn_007 === 1 && job.counts.modified === 1, 'the copy: CN-007 = 1 and 1 modified');
    await page.getByTestId('import-tab-modified').click();
    const rows = page.getByTestId('import-modified').getByTestId('rows-diff');
    assert((await rows.locator('[data-subcategory="0601"] [data-changed]').count()) === 2, 'the report: the 06-01 row, its description changed (before and after)');
    assert((await rows.locator('[data-subcategory="0602"] [data-changed]').count()) === 0, 'and the 06-02 row unchanged');
    assert((await page.getByTestId('import-modified').getByTestId('varies').textContent()).includes(es.import.variesBySubcategory), 'the description "varía por subcategoría"');
  });
  await page.getByTestId('catalog-tab-comparar').click();
  await page.getByTestId('compare-summary').waitFor();
  const compared = page.getByTestId('catalog-compare');
  await compared.getByTestId('rows-diff').waitFor();
  const variesText = await compared.getByTestId('varies').textContent();
  assert(variesText.includes('06-01') && variesText.includes('TBD') && variesText.includes('06-02') && variesText.includes('PTE'), '"Comparar": both values with their subcategory');
  await page.screenshot({ path: shot('verify-conf-fun-5-compare.png'), fullPage: true });
  await page.getByTestId('catalog-tab-versiones').click();
  await page.getByTestId(`version-menu-${second.number}`).click();
  assert(await page.getByTestId(`delete-version-${second.number}`).isDisabled(), 'the active version cannot be deleted');
  await page.keyboard.press('Escape');
  await page.getByTestId(`version-menu-${newest.number}`).click();
  await page.getByTestId(`delete-version-${newest.number}`).click();
  await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/api/catalog/versions/${newest.id}`) && r.request().method() === 'DELETE' && r.status() === 204),
    page.getByTestId('confirm-action').click(),
  ]);
  await page.getByTestId(`version-row-${newest.number}`).waitFor({ state: 'detached' });
  assert(true, `version ${newest.number} deleted from "Versiones"`);
  await signOut(page);

  // ── 6. The analyst reads, without importing ────────────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.goto(BASE_URL);
  // From the sidebar of their material: the module is available and opens
  // the common catalog, outside the material.
  const entry = page.getByTestId('sidebar-module-catalogo-normalizado');
  assert((await entry.getAttribute('data-status')) === 'disponible', 'the sidebar shows the module as available');
  await entry.click();
  await page.waitForURL('**/configuracion-funcional');
  await page.getByTestId('catalog-categories').waitFor();
  assert((await page.getByTestId('catalog-import').count()) === 0, 'the analyst has no "Importar"');
  assert((await page.getByTestId('catalog-export').count()) === 1, 'but can export');
  await page.screenshot({ path: shot('verify-conf-fun-4-analyst.png') });

  const unexpected = consoleErrors.filter((e) => !/\b401\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-conf-fun: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  purgeVerifyData(python, { importJobs, catalogVersions });
}
process.exit(failed ? 1 : 0);
