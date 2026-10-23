// E03: reference tables and the Excel import, in a real browser.
//   1. The admin opens D114 in Ajustes -> Tablas de referencia and sees its
//      13 values with their type (temporal / no temporal) by name.
//   2. They edit a D112 description inline (shown at once, saved: still
//      there after a reload).
//   3. They export D112 to Excel.
//   4. The file is changed with openpyxl (one description), as a person
//      would in Excel, and imported.
//   5. The report shows 1 modified value with its before -> after; applying
//      it changes the table.
//   6. The development analyst sees the tables (from the user menu) but no
//      edit, import, new value or deactivate action.
// Leaves the database as it was: D112 is saved before and put back after,
// versions included, and the import job is removed
// (backend/scripts/purge_verify_data.py); only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py and the data of seed_dev_data.py.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, or without the servers, it says so and exits 2 (NOT RUN).
//
//   node scripts/verify-reference-tables.mjs
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
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const STAMP = Date.now();
const INLINE_TEXT = `[verify] Editada en línea ${STAMP}`;
const EXCEL_TEXT = `[verify] Editada en Excel ${STAMP}`;
const SNAPSHOT = shot(`verify-reference-${STAMP}.json`);
const EXPORTED = shot(`verify-reference-D112-${STAMP}.xlsx`);
const EDITED = shot(`verify-reference-D112-${STAMP}-editado.xlsx`);

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
const purgeScript = path.join('scripts', 'purge_verify_data.py');
if (runBackendScript(python, 'save D112', [purgeScript, '--save-reference', 'D112', '--snapshot', SNAPSHOT]) !== 0) {
  notRun('could not save D112 before the check (is the database migrated?).');
}
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

const rows = (page) => page.getByTestId('reference-values').locator('tbody tr');

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. D114 with its types ─────────────────────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto(`${BASE_URL}/ajustes/tablas-referencia`);
  await page.getByTestId('reference-tables').waitFor();
  assert((await page.getByTestId('reference-tables').locator('tbody tr').count()) === 15, 'Ajustes lists the 15 reference tables');
  // The whole row opens the table (E11): a click on its name, not the link.
  const d114 = page.getByTestId('reference-row-D114');
  assert((await d114.getAttribute('data-nav-row')) !== null && (await d114.getByRole('button', { name: es.reference.openTable.replace('{{code}}', 'D114') }).count()) === 1, 'the row says it opens (chevron)');
  await d114.locator('td').nth(1).click();
  await page.getByTestId('reference-table-D114').waitFor();
  await rows(page).first().waitFor();
  assert((await rows(page).count()) === 13, 'D114 shows its 13 values');
  for (const code of ['02', '03', '04', '05']) {
    assert((await page.getByTestId(`value-row-${code}`).getByTestId('attr-tipo').textContent()) === 'Temporal', `D114 ${code} is "Temporal"`);
  }
  assert((await page.getByTestId('value-row-01').getByTestId('attr-tipo').textContent()) === 'No temporal', 'D114 01 is "No temporal"');
  assert(!(await page.getByTestId('reference-values').textContent()).includes('no_temporal'), 'no raw token on screen (HR21)');
  await page.screenshot({ path: shot('verify-reference-1-d114.png'), fullPage: true });

  // ── 2. Inline edit in D112 ─────────────────────────────────────────────
  await page.goto(`${BASE_URL}/ajustes/tablas-referencia/D112`);
  await rows(page).first().waitFor();
  const firstRow = rows(page).nth(0);
  const firstCode = (await firstRow.getAttribute('data-testid')).replace('value-row-', '');
  await firstRow.getByTestId('edit-value').click();
  await firstRow.getByTestId('edit-description').fill(INLINE_TEXT);
  const saved = page.waitForResponse((r) => r.url().includes('/api/reference-tables/D112/values/') && r.request().method() === 'PATCH');
  await firstRow.getByTestId('edit-save').click();
  assert((await firstRow.textContent()).includes(INLINE_TEXT), 'the edit shows at once (optimistic)');
  assert((await saved).ok(), 'the server saved the edit');
  await page.reload();
  await page.getByTestId(`value-row-${firstCode}`).waitFor();
  assert((await page.getByTestId(`value-row-${firstCode}`).textContent()).includes(INLINE_TEXT), 'after a reload the edit is still there');
  await page.screenshot({ path: shot('verify-reference-2-inline.png') });

  // ── 3. Export D112 ─────────────────────────────────────────────────────
  const secondCode = (await rows(page).nth(1).getAttribute('data-testid')).replace('value-row-', '');
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('reference-export').click()]);
  assert(download.suggestedFilename() === 'D112.xlsx', 'the export downloads D112.xlsx');
  await download.saveAs(EXPORTED);

  // ── 4. Change it with openpyxl and import ──────────────────────────────
  assert(runBackendScript(python, 'edit', [path.join('scripts', 'verify_edit_xlsx.py'), EXPORTED, EDITED, 'D112', `B3=${EXCEL_TEXT}`]) === 0, 'the workbook is edited with openpyxl');
  await page.getByTestId('reference-import').click();
  await page.getByTestId('import-file').setInputFiles(EDITED);
  const [started] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/reference-tables/D112/import') && r.request().method() === 'POST'),
    page.getByTestId('import-analyze').click(),
  ]);
  assert(started.status() === 202, 'the file is accepted for analysis');
  importJobs.push((await started.json()).id);

  // ── 5. The report: 1 modified; apply ───────────────────────────────────
  await page.getByTestId('import-report').waitFor();
  assert((await page.getByTestId('import-count-modified').textContent()) === '1', 'the report counts 1 modified');
  assert((await page.getByTestId('import-count-errors').textContent()) === '0', 'and no errors');
  assert((await page.getByTestId('import-count-unchanged').textContent()) === '81', 'and 81 unchanged (the inline edit included)');
  await page.getByTestId('import-tab-modified').click();
  const diff = await page.getByTestId('import-modified').textContent();
  assert(diff.includes(secondCode) && diff.includes(EXCEL_TEXT), 'the modified tab shows the value and its new description');
  await page.screenshot({ path: shot('verify-reference-3-report.png') });
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('/apply') && r.ok()),
    page.getByTestId('import-apply').click(),
  ]);
  await page.getByTestId('import-done').waitFor();
  assert(true, 'the import is applied');
  await page.screenshot({ path: shot('verify-reference-4-applied.png') });
  await page.keyboard.press('Escape');
  await page.getByTestId(`value-row-${secondCode}`).filter({ hasText: EXCEL_TEXT }).waitFor();
  assert(true, 'the table shows the imported description');
  await signOut(page);

  // ── 6. The analyst reads, without editing ──────────────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.getByTestId('user-menu').click();
  await page.getByTestId('reference-tables-link').click();
  await page.waitForURL('**/tablas-referencia');
  await page.getByTestId('reference-tables').waitFor();
  assert((await page.getByTestId('reference-tables').locator('tbody tr').count()) === 15, 'the analyst sees the 15 tables');
  await page.getByTestId('reference-row-D112').locator('td').nth(1).click();
  await rows(page).first().waitFor();
  await page.getByTestId('reference-read-only').waitFor();
  for (const id of ['edit-value', 'toggle-value', 'reference-import', 'reference-new-value']) {
    assert((await page.getByTestId(id).count()) === 0, `no "${id}" for the analyst`);
  }
  assert((await page.getByTestId('reference-export').count()) === 1, 'the analyst can export');
  assert((await page.getByTestId('settings-link').count()) === 0, 'and has no Settings');
  await page.screenshot({ path: shot('verify-reference-5-analyst.png'), fullPage: true });

  const unexpected = consoleErrors.filter((e) => !/\b401\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-reference-tables: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  runBackendScript(python, 'restore D112', [purgeScript, '--restore-reference', '--snapshot', SNAPSHOT]);
  purgeVerifyData(python, { importJobs });
}
process.exit(failed ? 1 : 0);
