// E17: baselines and change authorizations of the CONFUNFIS, in a real
// browser, with the demo loaded (as verify-validation) and its 10 blocking
// findings corrected first (backend/scripts/demo_corregir_hallazgos.py):
//   1. The analyst validates the Tramontana: no blocking finding.
//   2. Opens "Baselines y cambios" from the sidebar and creates v1: "En
//      revisión"; no "Aprobar" for its author; the CONFUNFIS says it is
//      read-only and "Nueva fila" is disabled.
//   3. The observer sees v1 without any action; the reviewer approves it:
//      "Revisada".
//   4. The CONFUNFIS needs an authorization: "Nueva fila" disabled, saying why.
//      The analyst requests AC-…-001 (LSA); the reviewer approves it.
//   5. The analyst chooses it as active in the band and changes the QTY of the
//      segments (A21031) from 3 to 4: total 24; the row's history names it.
//   6. Comparar v1 ↔ actual: 1 change (QTY 3 -> 4) with AC-…-001; to Excel.
//   7. "Exportar para entrega (baseline v1)": the zip of v1, warning of the
//      1 change not included.
//   8. Validates, creates v2, the reviewer approves it: AC-…-001 "Cerrada";
//      the Panel says "Baseline v2 revisada · 0 cambios desde v2".
//   9. The observer: neither "Validar ahora" nor "Exportar para entrega", but
//      the report.
// Leaves the database as it was: the CONFUNFIS and the articles are saved
// before and put back after (backend/scripts/purge_verify_data.py
// --save-confunfis / --save-articles), its baselines, authorizations and
// validations removed (--baselines, --authorizations, --validation-runs);
// only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD,
//   DEV_REVISOR_PASSWORD, DEV_OBSERVADOR_PASSWORD (the emails:
//   VERIFY_ANALISTA_EMAIL, VERIFY_REVISOR_EMAIL, VERIFY_OBSERVADOR_EMAIL, by
//   default those of backend/scripts/seed_dev_data.py)
// Without them, the servers or the demo data, it says so and exits 2.
//
//   node scripts/verify-baselines.mjs
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
const ANALYST = { email: process.env.VERIFY_ANALISTA_EMAIL || 'analista.dev@aal-dev.es', password: process.env.DEV_ANALISTA_PASSWORD };
const REVIEWER = { email: process.env.VERIFY_REVISOR_EMAIL || 'revisor.dev@aal-dev.es', password: process.env.DEV_REVISOR_PASSWORD };
const OBSERVER = { email: process.env.VERIFY_OBSERVADOR_EMAIL || 'observador.dev@aal-dev.es', password: process.env.DEV_OBSERVADOR_PASSWORD };
const TRAMONTANA = 'VTL 4X4 TRAMONTANA';
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const STAMP = Date.now();
const ROWS_SNAPSHOT = shot(`verify-baselines-rows-${STAMP}.json`);
const ARTICLES_SNAPSHOT = shot(`verify-baselines-articles-${STAMP}.json`);

function assert(cond, msg) {
  if (!cond) throw new Error('ASSERTION FAILED: ' + msg);
  console.log('OK:', msg);
}

if (!ADMIN_EMAIL || !ADMIN_PASSWORD || !ANALYST.password || !REVIEWER.password || !OBSERVER.password) {
  notRun('set VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD, DEV_REVISOR_PASSWORD and DEV_OBSERVADOR_PASSWORD.');
}
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const admin = await apiSession(BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD);
const tramontana = (await admin('GET', '/materials')).find((m) => m.name === TRAMONTANA);
if (!tramontana) notRun('no demo materials -- run backend/scripts/seed_demo_materials.py.');
const base = `/materials/${tramontana.id}`;
const summary = await admin('GET', `${base}/confunfis/summary`);
if (summary.rows !== 46) notRun(`the Tramontana has ${summary.rows} CONFUNFIS rows, not the demo's 46 -- run backend/scripts/seed_demo_confunfis.py.`);
if ((await admin('GET', `${base}/baselines`)).length) notRun('the Tramontana already has baselines -- run backend/scripts/seed_demo_confunfis.py --reset.');

const purge = path.join('scripts', 'purge_verify_data.py');
const runs = [];
if (runBackendScript(python, 'save the CONFUNFIS', [purge, '--save-confunfis', '--snapshot', ROWS_SNAPSHOT]) !== 0) notRun('could not save the CONFUNFIS rows.');
if (runBackendScript(python, 'save the articles', [purge, '--save-articles', '--snapshot', ARTICLES_SNAPSHOT]) !== 0) notRun('could not save the articles.');

async function signIn(page, { email, password }) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
  await page.getByTestId('user-menu').waitFor();
}

async function validate(page) {
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/validacion`);
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api${base}/validation`) && r.request().method() === 'POST'),
    page.getByTestId('validation-run').click(),
  ]);
  const body = await res.json();
  if (body.run_id) runs.push(body.run_id);
  return body;
}

async function openBaselines(page) {
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/baselines`);
  await page.getByTestId('baselines-timeline').waitFor();
}

/** "Aprobar" (with its optional comment) of a baseline or an authorization. */
async function approve(page, testid, dialog) {
  await page.getByTestId(testid).click();
  await page.getByTestId(dialog).waitFor();
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/approve') && r.request().method() === 'POST'),
    page.getByTestId(`${dialog}-confirm`).click(),
  ]);
  return res;
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  if (runBackendScript(python, 'demo_corregir_hallazgos', [path.join('scripts', 'demo_corregir_hallazgos.py')]) !== 0) throw new Error('demo_corregir_hallazgos.py failed');
  const consoleErrors = [];
  const contextFor = async (who) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
    await signIn(page, who);
    return page;
  };
  const page = await contextFor(ANALYST);

  // ── 1. Corrected and validated: no blocking finding ────────────────────
  const first = await validate(page);
  assert(first.blocking === 0 && !first.outdated, `the Tramontana corrected validates with no blocking finding (${first.state}, ${first.warnings} warnings)`);

  // ── 2. v1 in review: read-only CONFUNFIS, no "Aprobar" for its author ──
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}`);
  await page.getByTestId('sidebar-module-baselines').click();
  await page.waitForURL(`**/materiales/${tramontana.id}/baselines`);
  await page.getByTestId('baselines-empty').waitFor();
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api${base}/baselines`) && r.request().method() === 'POST'),
    page.getByTestId('baseline-create').click(),
  ]);
  assert(created.status() === 201, 'the analyst creates v1');
  const v1 = page.getByTestId('baseline-v1');
  await page.locator('[data-testid="baseline-v1"][data-state="en_revision"]').waitFor();
  assert((await page.getByTestId('baseline-v1-state').textContent()) === es.baselines.states.en_revision, 'v1 is "En revisión"');
  assert((await v1.getByTestId('baseline-v1-approve').count()) === 0, 'its author has no "Aprobar" (four eyes)');
  await page.screenshot({ path: shot('verify-baselines-1-v1.png'), fullPage: true });
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis`);
  await page.locator('[data-testid="confunfis-band"][data-state="locked"]').waitFor();
  assert(await page.getByTestId('confunfis-new-row').isDisabled(), 'the CONFUNFIS is read-only: "Nueva fila" disabled');

  // ── 3. The observer: no action; the reviewer approves v1 ───────────────
  const observer = await contextFor(OBSERVER);
  await openBaselines(observer);
  assert((await observer.getByTestId('baseline-v1-approve').count()) === 0 && (await observer.getByTestId('baseline-create').count()) === 0, 'the observer sees v1, without "Aprobar" nor "Crear baseline"');
  const reviewer = await contextFor(REVIEWER);
  await openBaselines(reviewer);
  assert((await approve(reviewer, 'baseline-v1-approve', 'baseline-review')).status() === 200, 'the reviewer approves v1');
  await reviewer.locator('[data-testid="baseline-v1"][data-state="revisada"]').waitFor();
  assert((await reviewer.getByTestId('baseline-v1-state').textContent()) === es.baselines.states.revisada, 'v1 is "Revisada"');

  // ── 4. An authorization: requested by the analyst, approved by the reviewer
  await page.reload();
  await page.locator('[data-testid="confunfis-band"][data-state="authorization"]').waitFor();
  assert(await page.getByTestId('confunfis-new-row').isDisabled(), 'with v1 reviewed, "Nueva fila" is disabled without an authorization');
  assert((await page.getByTestId('confunfis-edit-why').textContent()).startsWith(es.baselines.band.needAuthorization), 'saying an authorization is needed');
  // E17b: the row card's buttons are there, disabled, with the reason and the link that unblocks them; the observer has none.
  const rows = (await admin('GET', `${base}/confunfis/rows?page_size=1000`)).items;
  const segments = rows.find((r) => r.sns === 'A21031' && r.co === '01' && r.al === '00');
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?fila=${segments.id}`);
  await page.getByTestId('row-blocked').waitFor();
  for (const id of ['row-edit', 'row-duplicate-alternative', 'row-alternative-cs', 'row-delete', 'extra-function-add', 'incompatibility-add']) {
    assert(await page.getByTestId(id).isDisabled(), `analyst without an authorization: "${id}" shown, disabled`);
  }
  assert((await page.getByTestId('row-blocked').textContent()).includes(es.baselines.band.needAuthorization)
    && (await page.getByTestId('row-blocked-unlock').textContent()) === es.baselines.band.request, 'with the reason and "Solicitar una autorización"');
  await page.screenshot({ path: shot('verify-baselines-2-blocked.png') });
  await observer.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?fila=${segments.id}`);
  await observer.getByTestId('row-fields').waitFor();
  assert((await observer.getByTestId('row-edit').count()) === 0 && (await observer.getByTestId('row-blocked').count()) === 0
    && (await observer.getByTestId('extra-function-add').count()) === 0, 'the observer: no edit buttons at all');
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/baselines?tab=autorizaciones`);
  await page.getByTestId('authorization-new').click();
  await page.getByTestId('authorization-kind').click();
  await page.getByTestId('authorization-kind-lsa').click();
  await page.getByTestId('authorization-description').fill('Segmentos reforzados');
  await page.getByTestId('authorization-reason').fill('4 por pistón');
  const [asked] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api${base}/authorizations`) && r.request().method() === 'POST'),
    page.getByTestId('authorization-request-save').click(),
  ]);
  const ac = await asked.json();
  assert(asked.status() === 201 && /^AC-TRM-4X4-A-001$/.test(ac.code), `the analyst requests ${ac.code} (LSA)`);
  await page.getByTestId(`authorization-${ac.code}`).waitFor();
  assert((await page.getByTestId(`authorization-${ac.code}-approve`).count()) === 0, 'not approved by whoever requested it');
  await reviewer.goto(`${BASE_URL}/materiales/${tramontana.id}/baselines?tab=autorizaciones`);
  assert((await approve(reviewer, `authorization-${ac.code}-approve`, 'authorization-decide')).status() === 200, `the reviewer approves ${ac.code}`);

  // ── 5. Active in the band: the segments' QTY 3 -> 4, total 24 ──────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis?fila=${segments.id}`);
  await page.getByTestId('confunfis-authorization').click();
  await page.getByTestId(`confunfis-authorization-${ac.code}`).click();
  await page.getByTestId('row-blocked').waitFor({ state: 'detached' });
  assert(!(await page.getByTestId('row-edit').isDisabled()), `with ${ac.code} active, "Editar" is enabled`);
  await page.getByTestId('row-edit').click();
  await page.getByTestId('row-form-qty').fill('4');
  const [edited] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/confunfis/rows/') && r.request().method() === 'PATCH'),
    page.getByTestId('row-form-save').click(),
  ]);
  assert(edited.status() === 200 && edited.request().headers()['x-change-authorization'] === ac.id, `the edit goes under ${ac.code} (X-Change-Authorization)`);
  assert((await edited.json()).total === '24', 'the segments: QTY 4, total 24');
  await page.getByTestId('row-sheet').getByText(es.confunfis.card.historyAuthorization.replace('{{code}}', ac.code), { exact: false }).first().waitFor();
  assert(true, `the row's history names ${ac.code}`);
  await page.screenshot({ path: shot('verify-baselines-2-edit.png') });

  // ── 6. Comparar v1 ↔ actual: 1 change, with its authorization; Excel ────
  await openBaselines(page);
  await page.getByTestId('baseline-v1-compare').click();
  await page.getByTestId('diff-table').waitFor();
  const diffRows = page.getByTestId('diff-row');
  assert((await diffRows.count()) === 1, 'v1 ↔ actual: 1 change');
  const diffText = await diffRows.first().textContent();
  assert(diffText.includes('A21031 01 00') && diffText.includes(es.baselines.fields.qty) && (await page.getByTestId('diff-after').first().textContent()) === '4'
    && (await page.getByTestId('diff-authorization').first().textContent()) === ac.code, `the QTY of A21031, 3 -> 4, with ${ac.code}`);
  const [xlsx] = await Promise.all([page.waitForEvent('download'), page.getByTestId('diff-export').click()]);
  assert(/^COMPARACION_v1_.+\.xlsx$/.test(xlsx.suggestedFilename()), `exported to Excel (${xlsx.suggestedFilename()})`);
  await page.screenshot({ path: shot('verify-baselines-3-diff.png'), fullPage: true });

  // ── 7. The delivery is v1, warning of the change not included ──────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis`);
  const delivery = page.getByTestId('confunfis-delivery');
  await delivery.waitFor();
  await page.waitForFunction(() => document.querySelector('[data-testid="confunfis-delivery"]')?.textContent?.includes('v1'));
  assert(!(await delivery.isDisabled()), `"${await delivery.textContent()}" is enabled`);
  const [zip] = await Promise.all([page.waitForEvent('download'), delivery.click()]);
  const zipFile = shot(zip.suggestedFilename());
  await zip.saveAs(zipFile);
  assert(fs.readFileSync(zipFile).subarray(0, 2).toString() === 'PK', `the delivery is downloaded (${zip.suggestedFilename()})`);
  await page.getByText(es.baselines.delivery.notIncluded_one.replace('{{number}}', '1')).waitFor();
  assert(true, 'warning that 1 change is not included');

  // ── 8. v2: approving it closes the authorization; the Panel ────────────
  const second = await validate(page);
  assert(second.blocking === 0, 'validated again: no blocking finding');
  await openBaselines(page);
  await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api${base}/baselines`) && r.request().method() === 'POST'),
    page.getByTestId('baseline-create').click(),
  ]);
  await openBaselines(reviewer);
  assert((await approve(reviewer, 'baseline-v2-approve', 'baseline-review')).status() === 200, 'the reviewer approves v2');
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/baselines?tab=autorizaciones`);
  await page.locator(`[data-testid="authorization-${ac.code}"][data-state="cerrada"]`).waitFor();
  assert((await page.getByTestId(`authorization-${ac.code}`).textContent()).includes(es.baselines.authorizations.closedIn.replace('{{number}}', '2')), `${ac.code} is closed with v2`);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}`);
  const panel = page.getByTestId('panel-configuration-state');
  await page.waitForFunction(() => document.querySelector('[data-testid="panel-configuration-state"]')?.textContent?.includes('v2'));
  const panelText = await panel.textContent();
  assert(panelText.includes(es.baselines.band.reviewed.replace('{{number}}', '2')) && panelText.includes('0 cambios desde v2'), `the Panel: "${panelText}"`);
  await page.screenshot({ path: shot('verify-baselines-4-panel.png'), fullPage: true });

  // ── 8b. (E17b) The CUF's subcategories after v2: disabled, saying why; refused without an authorization ──
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/ficha`);
  await page.getByTestId('cuf-subcategories-blocked').waitFor();
  assert(await page.getByTestId('cuf-add-subcategory').isDisabled() && await page.getByTestId('cuf-remove-0201').isDisabled(),
    'the subcategories of the Tramontana: disabled, with the reason');
  const cuf = await admin('GET', `${base}/cuf`);
  const refused = await admin('PUT', `${base}/subcategories`, { version: cuf.version, codes: [...cuf.subcategories.map((x) => x.code), '0602'] })
    .then(() => 'accepted', (e) => e.message);
  assert(/answered 409: .*authorization_required/.test(refused), 'adding a subcategory without an authorization: 409 authorization_required');

  // ── 8c. (E17b) The admin creates v3 (every permission), but does not approve it (four eyes) ──
  const adminPage = await contextFor({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD });
  await openBaselines(adminPage);
  const [byAdmin] = await Promise.all([
    adminPage.waitForResponse((r) => r.url().endsWith(`/api${base}/baselines`) && r.request().method() === 'POST'),
    adminPage.getByTestId('baseline-create').click(),
  ]);
  assert(byAdmin.status() === 201, 'the admin sees "Crear baseline" and creates v3');
  await adminPage.locator('[data-testid="baseline-v3"][data-state="en_revision"]').waitFor();
  assert(await adminPage.getByTestId('baseline-v3-approve').isDisabled() && await adminPage.getByTestId('baseline-v3-reject').isDisabled()
    && (await adminPage.getByTestId('baseline-v3-four-eyes').count()) === 1, 'its "Aprobar" and "Rechazar" are disabled for the admin, its author (four eyes)');
  await adminPage.screenshot({ path: shot('verify-baselines-5-admin.png'), fullPage: true });

  // ── 9. The observer: no "Validar ahora" nor delivery, but the report ───
  await observer.goto(`${BASE_URL}/materiales/${tramontana.id}/validacion`);
  await observer.getByTestId('validation-page').waitFor();
  await observer.getByTestId('validation-light').waitFor();
  assert((await observer.getByTestId('validation-run').count()) === 0, 'the observer has no "Validar ahora" but sees the report');
  await observer.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis`);
  await observer.getByTestId('confunfis-export').waitFor();
  assert((await observer.getByTestId('confunfis-delivery').count()) === 0, 'nor "Exportar para entrega"');

  const unexpected = consoleErrors.filter((e) => !/\b(401|409)\b/.test(e));
  console.log(consoleErrors.length ? `console: ${consoleErrors.join(' | ')}` : 'console: clean');
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-baselines: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
  for (const context of browser.contexts()) {
    await context.pages()[0]?.screenshot({ path: shot(`verify-baselines-error-${browser.contexts().indexOf(context)}.png`) }).catch(() => undefined);
  }
} finally {
  await browser.close();
  const baselines = (await admin('GET', `${base}/baselines`)).map((b) => b.id);
  const authorizations = (await admin('GET', `${base}/authorizations`)).map((a) => a.id);
  runBackendScript(python, 'cleanup', [purge, '--authorizations', ...authorizations, '--baselines', ...baselines, '--validation-runs', ...runs]);
  runBackendScript(python, 'cleanup', [purge, '--restore-confunfis', '--snapshot', ROWS_SNAPSHOT]);
  runBackendScript(python, 'cleanup', [purge, '--restore-articles', '--snapshot', ARTICLES_SNAPSHOT]);
}
process.exit(failed ? 1 : 0);
