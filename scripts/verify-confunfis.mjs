// E13: the CONFUNFIS, in a real browser, with the demo loaded (catalog
// demo/CONF_FUN_DEMO.xlsx imported, backend/scripts/seed_demo_materials.py,
// seed_demo_articles.py and seed_demo_confunfis.py run).
//   1. The development analyst opens the CONFUNFIS of VTL 4X4 TRAMONTANA
//      from the sidebar.
//   2. Opens the motor and the pistón: the segments, QTY 3, total 18; their
//      card says "3 × 6 (A21030) × 1 (A20000) = 18". (E14) The search
//      "segmentos" opens the path and marks the row; "silentblock" walks 4.
//   3. Opens the radio (E12300, CUF montado) and jumps to its CONFUNFIS.
//   4. In the functional view, B35010 is outside the configuration.
//   5. Creates a row in A27010 (CO 04, suggested) with a provisional article
//      and duplicates it as an alternative: AL 01 and 02; (E14) removing the
//      copy takes the one left back to AL 00.
//   5b. (E14) The water pump's "Ver partes" shows 3 parts; the functional
//      products are 8, one observed (supply unit ZZ), O-1236 with N and E
//      together; on the radio's card, an extra function and an "excluye"
//      incompatibility are added and removed.
//   6. Tries to remove the subcategory 0102 from the Tramontana: refused,
//      the afuste C66100 uses it.
//   7. (E15) Exports the Tramontana's Anexo XI, imports it back in
//      "Fusionar": 0 new, 0 modified, 0 removed; applies it; downloads the
//      empty template.
// Leaves the database as it was: every CONFUNFIS row (with its products,
// extra functions and incompatibilities) and every article (with its parts)
// are saved before and put back after (backend/scripts/purge_verify_data.py
// --save-confunfis / --save-articles); only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, the servers or the demo data, it says so and exits 2.
//
//   node scripts/verify-confunfis.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';
import { apiSession, backendPythonOrNotRun, notRun, runBackendScript } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const ADMIN_EMAIL = process.env.VERIFY_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.VERIFY_ADMIN_PASSWORD;
const ANALYST_EMAIL = process.env.VERIFY_ANALISTA_EMAIL || 'analista.dev@aal-dev.es';
const ANALYST_PASSWORD = process.env.DEV_ANALISTA_PASSWORD;
const TRAMONTANA = 'VTL 4X4 TRAMONTANA';
const RADIO = 'RADIO VHF RT-500';
const NEW_NAME = 'SOPORTE MOTOR TRASERO IZQUIERDO';
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const ROWS_SNAPSHOT = shot(`verify-confunfis-rows-${Date.now()}.json`);
const ARTICLES_SNAPSHOT = shot(`verify-confunfis-articles-${Date.now()}.json`);

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
const admin = await apiSession(BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD);
const materials = await admin('GET', '/materials');
const tramontana = materials.find((m) => m.name === TRAMONTANA);
const radio = materials.find((m) => m.name === RADIO);
if (!tramontana || !radio) notRun('no demo materials -- run backend/scripts/seed_demo_materials.py.');
// (E15) The analyst's docked-panel width, given back at the end.
const analystApi = await apiSession(BASE_URL, ANALYST_EMAIL, ANALYST_PASSWORD);
const panelLimits = (await analystApi('GET', '/me/ui-settings')).detail_panel_width;
const panelWidth = (await analystApi('GET', '/auth/me')).ui_preferences.detail_panel_width ?? panelLimits.default;
const summary = await admin('GET', `/materials/${tramontana.id}/confunfis/summary`);
if (summary.rows !== 46) notRun(`the Tramontana has ${summary.rows} CONFUNFIS rows, not the demo's 46 -- run backend/scripts/seed_demo_confunfis.py.`);
const startCuf = await admin('GET', `/materials/${tramontana.id}/cuf`);

const purge = path.join('scripts', 'purge_verify_data.py');
const importJobs = [];
if (runBackendScript(python, 'save the CONFUNFIS', [purge, '--save-confunfis', '--snapshot', ROWS_SNAPSHOT]) !== 0) notRun('could not save the CONFUNFIS rows.');
if (runBackendScript(python, 'save the articles', [purge, '--save-articles', '--snapshot', ARTICLES_SNAPSHOT]) !== 0) notRun('could not save the articles.');

async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
  await page.getByTestId('user-menu').waitFor();
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  // Which request a "404" in the console was (the console text does not say).
  page.on('response', (r) => { if (r.status() === 404) consoleErrors.push(`404 ${r.request().method()} ${new URL(r.url()).pathname}`); });

  // ── 1. The analyst opens the Tramontana's CONFUNFIS ────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}`);
  await page.getByTestId('sidebar-module-confunfis').click();
  await page.waitForURL(`**/materiales/${tramontana.id}/confunfis`);
  await page.getByTestId('physical-tree').waitFor();
  assert((await page.getByTestId('confunfis-summary-rows').textContent()).includes('46'), 'the CONFUNFIS of the Tramontana: 46 rows');
  assert((await page.getByTestId('tree-row-000000-01-00').count()) === 1, 'the tree starts at the CUF, 000000 01 00');

  // ── 2. Motor -> pistón -> segments: total 18 ───────────────────────────
  await page.getByTestId('tree-toggle-A20000-01-00').click();
  await page.getByTestId('tree-toggle-A21030-01-00').click();
  const total = page.getByTestId('tree-total-A21031-01-00');
  await total.waitFor();
  assert((await total.textContent()).includes('total 18'), 'the segments (QTY 3) under the pistón: total 18 in the CUF');
  await page.getByTestId('tree-row-A21031-01-00').locator('button').last().click();
  const calculation = page.getByTestId('row-calculation');
  await calculation.waitFor();
  assert((await calculation.textContent()).includes('3 × 6 (A21030) × 1 (A20000) = 18'), 'their card: 3 × 6 (A21030) × 1 (A20000) = 18');
  await page.screenshot({ path: shot('verify-confunfis-1-tree.png') });
  // (E15) The card is docked: the tree stays visible and clickable beside it.
  const card = page.getByTestId('row-sheet');
  assert((await card.getAttribute('data-docked')) === 'true', 'the card is docked beside the tree (no overlay)');
  const treeBox = await page.getByTestId('physical-tree').boundingBox();
  const cardBox = await card.boundingBox();
  assert(treeBox && cardBox && treeBox.x + treeBox.width <= cardBox.x + 1, 'the tree narrows and stays visible, left of the card');
  await page.getByTestId('tree-row-A21030-01-00').locator('button').last().click();
  // By its label: the segments' card has "A21030 01 00" in it too (its CS).
  await page.locator('[data-testid="row-sheet"][aria-label^="A21030 01 00"]').waitFor();
  assert(true, 'another row of the tree opens its card without closing the panel');
  const widthBefore = cardBox.width;
  const [saved] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/me/ui-preferences') && r.request().method() === 'PUT'),
    (async () => { await page.getByTestId('detail-panel-resizer').focus(); await page.keyboard.press('ArrowLeft'); })(),
  ]);
  const widthAfter = (await card.boundingBox()).width;
  assert(saved.ok() && widthAfter > widthBefore && (await saved.json()).ui_preferences.detail_panel_width === Math.round(widthAfter), 'the card widens from its edge and the width is saved');
  await page.getByTestId('tree-row-A21030-01-00').locator('button').last().click();
  await card.waitFor({ state: 'detached' });
  assert(true, 'clicking its row again closes the card');
  await page.getByTestId('tree-row-A21031-01-00').locator('button').last().click();
  await card.waitFor();
  await page.keyboard.press('Escape');
  await card.waitFor({ state: 'detached' });
  assert(true, 'Esc closes the card');
  // (E14) The search opens the path to "segmentos" on a closed tree and marks it.
  await page.getByTestId('tree-collapse-all').click();
  await page.getByTestId('tree-search').fill('segmentos');
  await page.getByTestId('tree-search-count').filter({ hasText: '1 de 1' }).waitFor();
  await page.locator('[data-testid="tree-row-A21031-01-00"][data-hit="true"]').waitFor();
  assert(true, 'searching "segmentos" opens Motor -> Pistón and marks the row (1 de 1)');
  await page.getByTestId('tree-search').fill('silentblock');
  await page.getByTestId('tree-search-count').filter({ hasText: '1 de 4' }).waitFor();
  await page.getByTestId('tree-search-next').click();
  await page.getByTestId('tree-search-count').filter({ hasText: '2 de 4' }).waitFor();
  assert(true, '"silentblock": 4 hits, walked with "n de m"');
  await page.getByTestId('tree-search').fill('');

  // ── 3. The radio, CUF montado, to its own CONFUNFIS ────────────────────
  await page.getByTestId('confunfis-tab-tabla').click();
  await page.getByTestId('confunfis-search').fill('E12300');
  await page.getByTestId('confunfis-table-total').filter({ hasText: /^1 / }).waitFor();
  await page.getByTestId('confunfis-row-E12300-01-00').click();
  const mounted = page.getByTestId('row-mounted-link');
  await mounted.waitFor();
  assert((await mounted.textContent()).includes(RADIO), 'E12300 is the CUF of the RADIO VHF RT-500');
  await mounted.click();
  await page.waitForURL(`**/materiales/${radio.id}/confunfis`);
  await page.getByTestId('confunfis-page').waitFor();
  assert(true, 'its link opens the CONFUNFIS of the radio');
  await page.screenshot({ path: shot('verify-confunfis-2-radio.png') });

  // ── 4. The functional view: B35010 outside the configuration ───────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?tab=funcional`);
  const outside = page.getByTestId('functional-outside');
  await outside.waitFor();
  assert((await outside.textContent()).includes('B35010'), 'B35010 is outside the normalized configuration');
  await page.screenshot({ path: shot('verify-confunfis-3-functional.png') });

  // ── 5. A new row in A27010 CO 04, duplicated as an alternative ─────────
  await page.getByTestId('confunfis-new-row').click();
  const form = page.getByTestId('row-form');
  await form.waitFor();
  await page.getByTestId('row-form-sns').fill('A27010');
  await page.getByTestId('row-form-sns-hit').first().click();
  await page.waitForFunction(() => document.querySelector('[data-testid="row-form-co"]')?.value === '04');
  assert(true, 'CO 04 is suggested (01-03 are taken)');
  await page.getByTestId('row-form-name').fill(NEW_NAME);
  await page.getByTestId('row-form-function').fill('Sujetar el motor por detrás');
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/confunfis/rows`) && r.request().method() === 'POST'),
    page.getByTestId('row-form-save').click(),
  ]);
  const row = await created.json();
  assert(created.status() === 201 && row.article?.origin === 'confunfis' && `${row.sns} ${row.co} ${row.al}` === 'A27010 04 00', 'the row A27010 04 00 is created, with a provisional article');
  await page.getByTestId('row-sheet').filter({ hasText: NEW_NAME }).waitFor();
  const [duplicated] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/duplicate-alternative')),
    page.getByTestId('row-duplicate-alternative').click(),
  ]);
  assert(duplicated.status() === 201 && (await duplicated.json()).al === '02', 'duplicated as an alternative: AL 02');
  await page.getByTestId('row-sheet').filter({ hasText: 'A27010 04 02' }).waitFor();
  assert(true, 'the card of the copy opens');
  const rows = await admin('GET', `/materials/${tramontana.id}/confunfis/rows?sns=A27010&page_size=50`);
  const co04 = rows.items.filter((r) => r.co === '04').map((r) => r.al).sort();
  assert(JSON.stringify(co04) === '["01","02"]', 'A27010 CO 04 now has AL 01 and 02');
  await page.screenshot({ path: shot('verify-confunfis-4-alternative.png') });
  // (E14) Removing the copy offers to take the one left back to AL 00 (on by default).
  await page.getByTestId('row-delete').click();
  const offer = page.getByTestId('row-delete-reset-al');
  await offer.waitFor();
  assert((await offer.getAttribute('data-state')) === 'checked', 'removing the copy offers "Volver a AL 00", checked');
  const [removedCopy] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/confunfis/rows/') && r.request().method() === 'DELETE'),
    page.getByTestId('confirm-action').click(),
  ]);
  assert(removedCopy.status() === 204 && removedCopy.url().includes('reset_al=true'), 'the copy is removed');
  const after = await admin('GET', `/materials/${tramontana.id}/confunfis/rows?sns=A27010&page_size=50`);
  assert(JSON.stringify(after.items.filter((r) => r.co === '04').map((r) => r.al)) === '["00"]', 'the row left is A27010 04 00 again');
  await page.keyboard.press('Escape');

  // ── 5b (E14). Parts, functional products, extra function, incompatibility ─
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?tab=tabla`);
  await page.getByTestId('confunfis-search').fill('A22110');
  await page.getByTestId('confunfis-table-total').filter({ hasText: /^1 / }).waitFor();
  await page.getByTestId('confunfis-row-A22110-01-00').click();
  await page.getByTestId('row-parts-toggle').click();
  await page.getByTestId('row-parts-list').waitFor();
  assert((await page.getByTestId('row-part').count()) === 3, 'the water pump: "Ver partes" shows its 3 parts');
  await page.screenshot({ path: shot('verify-confunfis-6-parts.png') });
  await page.keyboard.press('Escape');

  // The module is on: the sidebar opens the tab, marked as the current page.
  await page.getByTestId('sidebar-module-productos-funcionales').click();
  await page.waitForURL(`**/materiales/${tramontana.id}/confunfis/productos`);
  await page.getByTestId('products-count').filter({ hasText: /^8 / }).waitFor();
  assert((await page.getByTestId('product-observation-OPF-004').count()) === 1, '8 functional products; one observation, the supply unit ZZ');
  assert((await page.getByTestId('product-group-O-1236').count()) === 1 && (await page.getByTestId('product-O-1236-N').count()) === 1 && (await page.getByTestId('product-O-1236-E').count()) === 1,
    'O-1236 groups its N and E rows');
  await page.screenshot({ path: shot('verify-confunfis-7-products.png') });

  const radioRow = (await admin('GET', `/materials/${tramontana.id}/confunfis/rows?sns=E12300&page_size=5`)).items[0];
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?fila=${radioRow.id}`);
  await page.getByTestId('extra-function-E19200').waitFor();
  assert(true, 'the radio has its extra function E19200');
  await page.getByTestId('extra-function-add').click();
  await page.getByTestId('extra-function-sns').fill('A21030');
  await page.getByTestId('extra-function-sns-hit').first().click();
  await page.getByTestId('extra-function-criterion').click();
  await page.getByRole('option', { name: 'Función más crítica' }).click();
  await page.getByTestId('extra-function-comment').fill('[verify] función adicional');
  const [extraMade] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/confunfis/extra-functions') && r.request().method() === 'POST'),
    page.getByTestId('extra-function-save').click(),
  ]);
  assert(extraMade.status() === 201, 'an extra function A21030 is added to the radio');
  await page.getByTestId('extra-function-A21030').waitFor();
  const [extraGone] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/confunfis/extra-functions/') && r.request().method() === 'DELETE'),
    (async () => { await page.getByTestId('extra-function-remove-A21030').click(); await page.getByTestId('confirm-action').click(); })(),
  ]);
  assert(extraGone.status() === 204 && (await page.getByTestId('extra-function-A21030').count()) === 0, 'and removed');

  await page.getByTestId('incompatibility-add').click();
  await page.getByTestId('incompatibility-row').fill('A21030');
  await page.getByTestId('incompatibility-row-hit').first().click();
  await page.getByTestId('incompatibility-reason').fill('[verify] no caben juntos');
  const [incMade] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/confunfis/incompatibilities') && r.request().method() === 'POST'),
    page.getByTestId('incompatibility-save').click(),
  ]);
  assert(incMade.status() === 201 && (await incMade.json()).kind === 'excluye', 'an "excluye" incompatibility with the pistón is added');
  await page.getByTestId('incompatibility-excluye').waitFor();
  await page.screenshot({ path: shot('verify-confunfis-8-incompatibility.png') });
  const [incGone] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/confunfis/incompatibilities/') && r.request().method() === 'DELETE'),
    (async () => { await page.getByTestId('incompatibility-remove').click(); await page.getByTestId('confirm-action').click(); })(),
  ]);
  assert(incGone.status() === 204, 'and removed');
  await page.keyboard.press('Escape');

  // ── 6. 0102 cannot leave the Tramontana ────────────────────────────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/ficha`);
  await page.getByTestId('cuf-subcategories').waitFor();
  const [refused] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/materials/${tramontana.id}/subcategories`) && r.request().method() === 'PUT'),
    page.getByTestId('cuf-remove-0102').click(),
  ]);
  assert(refused.status() === 409 && (await refused.json()).detail.code === 'subcategory_used_by_confunfis', 'removing 0102 is refused: the CONFUNFIS uses it');
  await page.getByText('C66100').first().waitFor();
  assert(true, 'the message names the row (C66100, the afuste)');
  await page.getByTestId('cuf-sub-0102').waitFor();
  assert(true, '0102 is still there');
  await page.screenshot({ path: shot('verify-confunfis-5-guard.png') });

  // ── 7 (E15). Anexo XI out and back in, 0 changes; the empty template ──
  // Step 5 left one row more than the demo: what is there now is what goes out.
  const now7 = await admin('GET', `/materials/${tramontana.id}/confunfis/summary`);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis`);
  await page.getByTestId('physical-tree').waitFor();
  await page.getByTestId('confunfis-export').click();
  const [anexo] = await Promise.all([page.waitForEvent('download'), page.getByTestId('confunfis-export-anexo').click()]);
  const anexoFile = shot(anexo.suggestedFilename());
  await anexo.saveAs(anexoFile);
  assert(/^ANEXO_XI_.+_\d{8}\.xlsx$/.test(anexo.suggestedFilename()) && fs.statSync(anexoFile).size > 0, `the Anexo XI is downloaded (${anexo.suggestedFilename()})`);
  await page.getByTestId('confunfis-import').click();
  await page.getByTestId('confunfis-import-anexo').click();
  await page.getByTestId('book-import').waitFor();
  assert(await page.getByTestId('book-mode-merge').getAttribute('aria-checked') === 'true', '"Fusionar" is the default mode');
  assert(await page.getByTestId('book-mode-replace').isDisabled(), '"Sustituir" is not offered to the analyst');
  await page.getByTestId('book-file').setInputFiles(anexoFile);
  const [started] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/confunfis/import?mode=merge`) && r.request().method() === 'POST'),
    page.getByTestId('book-analyze').click(),
  ]);
  importJobs.push((await started.json()).id);
  await page.getByTestId('book-report').waitFor({ timeout: 60000 });
  await page.getByTestId('book-apply').waitFor();
  const job = await analystApi('GET', `/import-jobs/${importJobs[0]}`);
  const c = job.counts;
  assert(c.new === 0 && c.modified === 0 && c.removed === 0 && c.rejected === 0 && c.unchanged >= now7.rows,
    `the book comes back with 0 changes (unchanged ${c.unchanged}: ${c.rows_unchanged} rows, ${c.products_unchanged} products, ${c.parts_unchanged} parts)`);
  assert(await page.getByTestId(`book-count-CON_FUN_FIS-unchanged`).innerText() === String(now7.rows), `the CON_FUN_FIS tab says ${now7.rows} unchanged`);
  await page.getByTestId('book-sheet-result').click();
  await page.getByTestId('book-result-observations').waitFor();
  await page.screenshot({ path: shot('verify-confunfis-9-book-import.png') });
  const [applied] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/confunfis/import/${importJobs[0]}/apply`)),
    page.getByTestId('book-apply').click(),
  ]);
  assert(applied.status() === 200, 'applying it is accepted');
  await page.getByTestId('book-done').waitFor();
  await page.getByTestId('book-close').click();
  const after7 = await admin('GET', `/materials/${tramontana.id}/confunfis/summary`);
  assert(after7.rows === now7.rows, `the CONFUNFIS still has ${now7.rows} rows`);
  await page.getByTestId('confunfis-export').click();
  const [template] = await Promise.all([page.waitForEvent('download'), page.getByTestId('confunfis-export-plantilla').click()]);
  const templateFile = shot(template.suggestedFilename());
  await template.saveAs(templateFile);
  assert(/^PLANTILLA_CONFUNFIS_.+\.xlsx$/.test(template.suggestedFilename()) && fs.statSync(templateFile).size > 0, `the empty template is downloaded (${template.suggestedFilename()})`);

  const unexpected = consoleErrors.filter((e) => !/\b(401|409)\b/.test(e));
  console.log(consoleErrors.length ? `console: ${consoleErrors.join(' | ')}` : 'console: clean');
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-confunfis: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
  await browser.contexts()[0]?.pages()[0]?.screenshot({ path: shot('verify-confunfis-error.png') }).catch(() => undefined);
} finally {
  await browser.close();
  if (importJobs.length) runBackendScript(python, 'cleanup', [purge, '--import-jobs', ...importJobs]);
  runBackendScript(python, 'cleanup', [purge, '--restore-confunfis', '--snapshot', ROWS_SNAPSHOT]);
  runBackendScript(python, 'cleanup', [purge, '--restore-articles', '--snapshot', ARTICLES_SNAPSHOT]);
  await analystApi('PUT', '/me/ui-preferences', { detail_panel_width: panelWidth }).catch(() => undefined);
  // Had the guard failed, the Tramontana gets its subcategories back.
  const now = await admin('GET', `/materials/${tramontana.id}/cuf`);
  const codes = startCuf.subcategories.map((s) => s.code);
  if (JSON.stringify(now.subcategories.map((s) => s.code)) !== JSON.stringify(codes)) {
    await admin('PUT', `/materials/${tramontana.id}/subcategories`, { version: now.version, codes });
    console.log('cleanup: subcategorías devueltas');
  }
}
process.exit(failed ? 1 : 0);
