// E11: Materials / CUF, in a real browser, with demo/CONF_FUN_DEMO.xlsx
// imported and backend/scripts/seed_demo_materials.py run.
//   1. The development analyst opens the card of VTL 4X4 TRAMONTANA.
//   2. Removes the subcategory 0102 (62 SNS) and adds it back (65); with the
//      demo CONFUNFIS loaded (E13), the removal is refused instead.
//   3. Opens "Configuración normalizada" and searches E12300 (from 0201).
//   4. Creates a request for a new SNS and sends it; (E12) creates a draft
//      and discards it ("Descartar borrador").
//   5. (E12) The admin annuls the sent request with a reason: it leaves the
//      list and comes back with "Mostrar anuladas", marked annulled.
//   6. The admin creates a temporary CUF "a partir de otro" from Settings ->
//      Materiales, opens it from its row, and checks it is independent: a
//      subcategory removed from it does not leave the original.
// Leaves the database as it was: the Tramontana gets its three subcategories
// back, the request and the temporary CUF ("[verify] …") are removed
// (backend/scripts/purge_verify_data.py); only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py, the data of seed_dev_data.py and
// seed_demo_materials.py, and the demo catalog imported. Credentials from
// the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, the servers or the demo data, it says so and exits 2.
//
//   node scripts/verify-materials.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';
import { apiSession, backendPythonOrNotRun, notRun, purgeVerifyData } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const ADMIN_EMAIL = process.env.VERIFY_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.VERIFY_ADMIN_PASSWORD;
const ANALYST_EMAIL = process.env.VERIFY_ANALISTA_EMAIL || 'analista.dev@aal-dev.es';
const ANALYST_PASSWORD = process.env.DEV_ANALISTA_PASSWORD;
const TRAMONTANA = 'VTL 4X4 TRAMONTANA';
const COPY_NAME = `[verify] CUF temporal ${Date.now()}`;
const REQUEST_NAME = `[verify] Sistema de vigilancia perimetral ${Date.now()}`;
const DRAFT_NAME = `[verify] Borrador descartado ${Date.now()}`;
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const count = (n) => es.cuf.snsCount.replace('{{count}}', n);

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
const tramontana = (await admin('GET', '/materials')).find((m) => m.name === TRAMONTANA);
if (!tramontana) notRun(`no "${TRAMONTANA}" -- run backend/scripts/seed_demo_materials.py.`);
const startCuf = await admin('GET', `/materials/${tramontana.id}/cuf`);
if (startCuf.sns_count !== 65) notRun('the Tramontana has not its demo subcategories -- import demo/CONF_FUN_DEMO.xlsx and run seed_demo_materials.py.');
const snsRequests = [];
const confunfisRows = (await admin('GET', `/materials/${tramontana.id}/confunfis/summary`)).rows;

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

const putSubcategories = (page) => page.waitForResponse((r) => r.url().endsWith(`/api/materials/${tramontana.id}/subcategories`) && r.request().method() === 'PUT');

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. The analyst opens the Tramontana's card ─────────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}`);
  await page.getByTestId(`sidebar-module-materiales`).click();
  await page.waitForURL(`**/materiales/${tramontana.id}/ficha`);
  await page.getByTestId('cuf-subcategories').waitFor();
  assert((await page.getByTestId('cuf-sns-count').textContent()) === count(65), 'the Tramontana: 65 SNS');
  assert((await page.getByTestId('cuf-family').textContent()).includes(`${TRAMONTANA} PUESTO DE MANDO`), 'its variant, the Puesto de mando');
  assert((await page.getByTestId('cuf-version-label').count()) === 1 && (await page.getByTestId('cuf-change-version').count()) === 0, 'its catalog version; no change for the analyst');
  await page.screenshot({ path: shot('verify-materials-1-card.png'), fullPage: true });

  // ── 2. Remove 0102 and add it back ─────────────────────────────────────
  // (E13) With the demo CONFUNFIS loaded, its afuste (C66100) uses an SNS
  // only 0102 brings: the removal is refused and the chip comes back.
  if (confunfisRows > 0) {
    const refused = putSubcategories(page);
    await page.getByTestId('cuf-remove-0102').click();
    assert((await refused).status() === 409, 'with a CONFUNFIS using it, 0102 cannot leave (E13)');
    await page.getByTestId('cuf-sub-0102').waitFor();
    assert((await page.getByTestId('cuf-sns-count').textContent()) === count(65), 'the chip comes back: 65 SNS');
  } else {
    const removed = putSubcategories(page);
    await page.getByTestId('cuf-remove-0102').click();
    await page.getByTestId('cuf-sub-0102').waitFor({ state: 'detached', timeout: 2000 });
    assert(true, 'the chip leaves at once (optimistic)');
    assert((await removed).ok(), 'the server saved it');
    await page.getByTestId('cuf-sns-count').filter({ hasText: count(62) }).waitFor();
    assert(true, 'without 0102: 62 SNS');
    await page.getByTestId('cuf-add-subcategory').click();
    const added = putSubcategories(page);
    await page.getByTestId('cuf-option-0102').click();
    assert((await added).ok(), '0102 added back');
    await page.getByTestId('cuf-sns-count').filter({ hasText: count(65) }).waitFor();
    assert(true, 'with 0102 again: 65 SNS');
  }

  // ── 3. The normalized configuration ────────────────────────────────────
  await page.getByTestId('cuf-tab-configuracion').click();
  await page.getByTestId('cuf-normalized').waitFor();
  await page.getByTestId('tree-node-000000').waitFor();
  assert((await page.getByTestId('origin-000000-0102').count()) === 1, 'the tree shows the subcategories of origin (000000 from the three)');
  await page.getByTestId('cuf-search').fill('E12300');
  const hit = page.getByTestId('cuf-hit-E12300');
  await hit.waitFor();
  assert((await hit.textContent()).includes('0201'), 'E12300 is found, from 0201');
  await hit.click();
  await page.getByTestId('sns-card').filter({ hasText: 'E12300' }).waitFor();
  await page.screenshot({ path: shot('verify-materials-2-config.png'), fullPage: true });

  // ── 4. A request for a new SNS, sent ───────────────────────────────────
  await page.getByTestId('cuf-tab-solicitudes').click();
  await page.getByTestId('sns-request-new').click();
  const form = page.getByTestId('sns-request-form');
  await form.getByLabel(es.cuf.requests.parentSns).fill('E10000');
  await form.getByLabel(es.cuf.requests.name).fill(REQUEST_NAME);
  await form.getByLabel(es.cuf.requests.justification).fill('No existe en la configuración normalizada del CUF.');
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/sns-requests') && r.request().method() === 'POST'),
    page.getByTestId('sns-request-save').click(),
  ]);
  snsRequests.push((await created.json()).id);
  const row = page.getByTestId(`sns-request-${REQUEST_NAME}`);
  await row.waitFor();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/submit') && r.ok()), row.getByTestId('sns-request-send').click()]);
  await row.getByTestId('sns-request-state').filter({ hasText: es.cuf.requests.states.enviada }).waitFor();
  assert(true, 'the request is sent');
  await page.screenshot({ path: shot('verify-materials-3-request.png') });
  // A draft, discarded by its author.
  await page.getByTestId('sns-request-new').click();
  await form.getByLabel(es.cuf.requests.name).fill(DRAFT_NAME);
  await form.getByLabel(es.cuf.requests.justification).fill('Se descarta en la prueba.');
  const [draft] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/sns-requests') && r.request().method() === 'POST'),
    page.getByTestId('sns-request-save').click(),
  ]);
  snsRequests.push((await draft.json()).id);
  const draftRow = page.getByTestId(`sns-request-${DRAFT_NAME}`);
  await draftRow.getByTestId('sns-request-discard').click();
  await Promise.all([page.waitForResponse((r) => r.request().method() === 'DELETE' && r.status() === 204), page.getByTestId('confirm-action').click()]);
  await draftRow.waitFor({ state: 'detached' });
  assert((await row.getByTestId('sns-request-discard').count()) === 0, 'a draft is discarded with its button; a sent one has none');
  await signOut(page);

  // ── 5. The admin annuls the sent request ───────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/ficha?tab=solicitudes`);
  await row.getByTestId('sns-request-annul').click();
  const annulDialog = page.getByTestId('sns-request-annul-dialog');
  assert(await annulDialog.getByTestId('sns-request-annul-confirm').isDisabled(), 'annulling needs a reason');
  await annulDialog.getByTestId('sns-request-annul-reason').fill('Duplicada de otra solicitud.');
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/annul') && r.status() === 204), annulDialog.getByTestId('sns-request-annul-confirm').click()]);
  await row.waitFor({ state: 'detached' });
  assert(true, 'the annulled request leaves the list');
  await page.getByTestId('sns-requests-show-annulled').click();
  await row.getByTestId('sns-request-annulled').waitFor();
  assert((await row.textContent()).includes('Duplicada de otra solicitud.'), '"Mostrar anuladas" brings it back, with its reason');
  await page.screenshot({ path: shot('verify-materials-3b-annulled.png') });

  // ── 6. The admin copies the Tramontana ─────────────────────────────────
  await page.goto(`${BASE_URL}/ajustes/materiales`);
  const source = page.getByTestId(`material-row-${TRAMONTANA}`);
  await source.getByRole('button', { name: es.actions.more }).click();
  await page.getByTestId(`copy-${TRAMONTANA}`).click();
  const dialog = page.getByTestId('copy-material');
  await dialog.getByLabel(es.material.fields.name).fill(COPY_NAME);
  const [copied] = await Promise.all([page.waitForResponse((r) => r.url().endsWith('/copy') && r.request().method() === 'POST'), dialog.getByTestId('copy-save').click()]);
  assert(copied.status() === 201, 'the copy is created');
  const copy = await copied.json();
  // The whole row opens the card.
  await page.getByTestId(`material-row-${COPY_NAME}`).locator('td').first().click();
  await page.waitForURL(`**/materiales/${copy.id}/ficha`);
  await page.getByTestId('cuf-sns-count').filter({ hasText: count(65) }).waitFor();
  assert((await page.getByTestId('cuf-family').textContent()).includes(TRAMONTANA), 'the copy says it is a variant of the Tramontana');
  if (confunfisRows > 0) {
    // (E13) The copy carries the CONFUNFIS; a row removed from it stays in the original.
    const copied = await admin('GET', `/materials/${copy.id}/confunfis/rows?page_size=1000`);
    assert(copied.total === confunfisRows && copied.items.every((r) => r.source === 'copia'), `the copy carries the CONFUNFIS (${copied.total} rows)`);
    const one = copied.items[0];
    await admin('DELETE', `/materials/${copy.id}/confunfis/rows/${one.id}?version=${one.version}&confirm=true`);
    const kept = await admin('GET', `/materials/${tramontana.id}/confunfis/summary`);
    assert(kept.rows === confunfisRows, 'independent: the original keeps all its CONFUNFIS rows');
  } else {
    await Promise.all([
      page.waitForResponse((r) => r.url().endsWith(`/api/materials/${copy.id}/subcategories`) && r.ok()),
      page.getByTestId('cuf-remove-0102').click(),
    ]);
    await page.getByTestId('cuf-sns-count').filter({ hasText: count(62) }).waitFor();
    const original = await admin('GET', `/materials/${tramontana.id}/cuf`);
    assert(original.sns_count === 65 && original.subcategories.length === 3, 'independent: the original keeps its 65 SNS');
  }
  await page.screenshot({ path: shot('verify-materials-4-copy.png'), fullPage: true });

  // The 409 of the refused removal (E13) is expected.
  const unexpected = consoleErrors.filter((e) => !/\b401\b/.test(e) && !(confunfisRows > 0 && /\b409\b/.test(e)));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-materials: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  // A change the browser sent just before closing may still be on its way.
  await new Promise((resolve) => setTimeout(resolve, 1000));
  const now = await admin('GET', `/materials/${tramontana.id}/cuf`);
  const codes = startCuf.subcategories.map((s) => s.code);
  if (now.subcategories.map((s) => s.code).join() !== codes.join()) {
    await admin('PUT', `/materials/${tramontana.id}/subcategories`, { version: now.version, codes });
    console.log('cleanup: the Tramontana gets its subcategories back');
  }
  purgeVerifyData(python, { snsRequests, materials: [COPY_NAME] });
}
process.exit(failed ? 1 : 0);
