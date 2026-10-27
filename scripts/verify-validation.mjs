// E16: the NT 10/17 validator, in a real browser, with the demo loaded
// (catalog demo/CONF_FUN_DEMO.xlsx imported, backend/scripts/
// seed_demo_materials.py, seed_demo_articles.py and seed_demo_confunfis.py run).
//   1. The development analyst opens "Validación NT 10/17" of VTL 4X4
//      TRAMONTANA from the sidebar and validates it: red, the 6 blocking
//      findings of the CONFUNFIS (CF-001, 002, 007, 012, 014, 015) plus the
//      AR ones of its articles.
//   2. Presses CF-007 and its "Ir a": the FILTRO DE AIRE opens in the tree,
//      with its card and the CS marked.
//   3. Changes its CS to A20000 01 00 (the motor): the report is
//      "desactualizado"; validated again, CF-007 is gone.
//   4. "Exportar para entrega" is disabled in the CONFUNFIS, saying why.
//   5. Accepts the CF-017 warning (the tyre) with a justification.
//   6. Downloads the report as PDF.
//   7. The admin turns CF-018 off in Ajustes -> Reglas de validación: the
//      report is "desactualizado" (the rules changed); and back on.
// Leaves the database as it was: the CONFUNFIS rows are saved before and
// put back after (backend/scripts/purge_verify_data.py --save-confunfis),
// its validations and the acceptance are removed (--validation-runs,
// --accepted-findings) and CF-018 is left as it was; only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, the servers or the demo data, it says so and exits 2.
//
//   node scripts/verify-validation.mjs
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
const BLOCKING_CF = ['CF-001', 'CF-002', 'CF-007', 'CF-012', 'CF-014', 'CF-015'];
const JUSTIFICATION = 'Neumático también en cadenas: error de demo conocido';
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const ROWS_SNAPSHOT = shot(`verify-validation-rows-${Date.now()}.json`);

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
if (!tramontana) notRun('no demo materials -- run backend/scripts/seed_demo_materials.py.');
const summary = await admin('GET', `/materials/${tramontana.id}/confunfis/summary`);
if (summary.rows !== 46) notRun(`the Tramontana has ${summary.rows} CONFUNFIS rows, not the demo's 46 -- run backend/scripts/seed_demo_confunfis.py.`);
const ruleBefore = (await admin('GET', '/validation-rules')).find((r) => r.code === 'CF-018');

const purge = path.join('scripts', 'purge_verify_data.py');
const runs = [];
const accepted = [];
if (runBackendScript(python, 'save the CONFUNFIS', [purge, '--save-confunfis', '--snapshot', ROWS_SNAPSHOT]) !== 0) notRun('could not save the CONFUNFIS rows.');

async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
  await page.getByTestId('user-menu').waitFor();
}

/** "Validar ahora", keeping the run's id for the cleanup. */
async function validate(page) {
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/materials/${tramontana.id}/validation`) && r.request().method() === 'POST'),
    page.getByTestId('validation-run').click(),
  ]);
  const body = await res.json();
  if (body.run_id) runs.push(body.run_id);
  return body;
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. The analyst validates the Tramontana: red ───────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}`);
  await page.getByTestId('sidebar-module-validacion').click();
  await page.waitForURL(`**/materiales/${tramontana.id}/validacion`);
  await page.getByTestId('validation-page').waitFor();
  const first = await validate(page);
  await page.locator('[data-testid="validation-light"][data-state="red"]').waitFor();
  const blockingCf = first.by_rule.filter((r) => r.code.startsWith('CF-') && r.severity === 'bloqueante');
  assert(JSON.stringify(blockingCf.map((r) => r.code)) === JSON.stringify(BLOCKING_CF) && blockingCf.every((r) => r.findings === 1),
    `red: the 6 blocking findings of the CONFUNFIS (${BLOCKING_CF.join(', ')})`);
  const ar = first.by_rule.filter((r) => r.code.startsWith('AR-')).map((r) => `${r.code} ${r.severity}`);
  assert(ar.length >= 4 && first.blocking > 6, `plus the AR ones of its articles (${ar.join(', ')}; ${first.blocking} blocking in all)`);
  for (const code of BLOCKING_CF) assert((await page.getByTestId(`validation-rule-${code}`).count()) === 1, `${code} in the summary by rule`);
  await page.screenshot({ path: shot('verify-validation-1-red.png'), fullPage: true });

  // ── 2. CF-007 -> "Ir a": the air filter in the tree, with its card ──────
  await page.getByTestId('validation-rule-CF-007').click();
  const cf007 = page.getByTestId('finding-CF-007');
  await cf007.waitFor();
  assert((await page.locator('tr[data-testid^="finding-"]').count()) === 1, 'pressing CF-007 leaves only its finding');
  assert((await cf007.textContent()).includes('A24110 01 00'), 'the finding is the FILTRO DE AIRE, A24110 01 00');
  await cf007.getByTestId('finding-goto').click();
  await page.waitForURL(`**/materiales/${tramontana.id}/confunfis?**`);
  const card = page.locator('[data-testid="row-sheet"][aria-label^="A24110 01 00"]');
  await card.waitFor();
  await page.locator('[data-testid="tree-row-A24110-01-00"][data-hit="true"]').waitFor();
  assert((await page.getByTestId('row-field-marked').count()) === 1, '"Ir a" opens the row in the tree, with its card and the CS marked');
  await page.screenshot({ path: shot('verify-validation-2-goto.png') });

  // ── 3. Its CS to A20000 01 00: outdated, validated again, CF-007 gone ──
  await page.getByTestId('row-edit').click();
  await page.getByTestId('row-form').waitFor();
  await page.getByTestId('row-form-cs-picked').getByRole('button').click();
  await page.getByTestId('row-form-cs').fill('A20000');
  await page.getByTestId('row-form-cs-hit').filter({ hasText: 'A20000 01 00' }).first().click();
  const [edited] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/confunfis/rows/') && r.request().method() === 'PATCH'),
    page.getByTestId('row-form-save').click(),
  ]);
  assert(edited.status() === 200 && (await edited.json()).cs_sns === 'A20000', 'the CS of the air filter is now A20000 01 00 (the motor)');
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/validacion`);
  await page.getByTestId('validation-outdated').waitFor();
  assert(true, 'the report is "desactualizado"');
  const second = await validate(page);
  await page.getByTestId('validation-outdated').waitFor({ state: 'detached' });
  assert(!second.by_rule.some((r) => r.code === 'CF-007') && second.blocking === first.blocking - 1, `validated again: CF-007 is gone (${second.blocking} blocking)`);

  // ── 4. "Exportar para entrega" is disabled, saying why ─────────────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/confunfis`);
  await page.getByTestId('confunfis-summary-findings').waitFor();
  const delivery = page.getByTestId('confunfis-delivery');
  assert(await delivery.isDisabled(), '"Exportar para entrega" is disabled');
  const why = await page.getByTestId('confunfis-delivery-why').textContent();
  assert(why.includes(String(second.blocking)) && /bloqueantes/.test(why), `and says why: "${why}"`);
  await page.screenshot({ path: shot('verify-validation-3-delivery.png') });

  // ── 5. The CF-017 warning accepted with a justification ────────────────
  await page.goto(`${BASE_URL}/materiales/${tramontana.id}/validacion`);
  const tyre = page.getByTestId('finding-CF-017');
  await tyre.waitFor();
  const tyreId = second.findings.find((f) => f.rule_code === 'CF-017').id;
  await tyre.getByTestId('finding-accept').click();
  await page.getByTestId('accept-justification').fill(JUSTIFICATION);
  const [acceptRes] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/accept') && r.request().method() === 'POST'),
    page.getByTestId('accept-save').click(),
  ]);
  accepted.push(tyreId);
  assert(acceptRes.status() === 200, 'the CF-017 warning (the tyre) is accepted');
  await tyre.getByTestId('finding-accepted').waitFor();
  assert((await tyre.textContent()).includes(JUSTIFICATION), 'it shows as accepted, with its justification');
  await page.getByTestId('validation-accepted').waitFor();

  // ── 6. The report as PDF ───────────────────────────────────────────────
  const [pdf] = await Promise.all([page.waitForEvent('download'), page.getByTestId('validation-export-pdf').click()]);
  const pdfFile = shot(pdf.suggestedFilename());
  await pdf.saveAs(pdfFile);
  assert(/^VALIDACION_NT_.+\.pdf$/.test(pdf.suggestedFilename()) && fs.readFileSync(pdfFile).subarray(0, 4).toString() === '%PDF', `the report is downloaded as PDF (${pdf.suggestedFilename()})`);
  await page.screenshot({ path: shot('verify-validation-4-report.png'), fullPage: true });

  // ── 7. The admin turns CF-018 off: the report is outdated ──────────────
  const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const adminPage = await adminContext.newPage();
  adminPage.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  await signIn(adminPage, ADMIN_EMAIL, ADMIN_PASSWORD);
  await adminPage.goto(`${BASE_URL}/ajustes/reglas-validacion`);
  const toggle = adminPage.getByTestId('rule-active-CF-018');
  await toggle.waitFor();
  const [off] = await Promise.all([
    adminPage.waitForResponse((r) => r.url().endsWith('/api/validation-rules/CF-018') && r.request().method() === 'PATCH'),
    toggle.click(),
  ]);
  assert(off.status() === 200 && (await off.json()).active === false, 'the admin turns CF-018 off in Ajustes -> Reglas de validación');
  await adminPage.screenshot({ path: shot('verify-validation-5-rules.png') });
  await page.reload();
  await page.getByTestId('validation-outdated').waitFor();
  assert((await page.getByTestId('validation-when').textContent()).includes(es.validation.page.outdatedRules), 'the report is "desactualizado": the rules changed');
  const [on] = await Promise.all([
    adminPage.waitForResponse((r) => r.url().endsWith('/api/validation-rules/CF-018') && r.request().method() === 'PATCH'),
    toggle.click(),
  ]);
  assert(on.status() === 200 && (await on.json()).active === true, 'and turns it back on');

  const unexpected = consoleErrors.filter((e) => !/\b(401|409)\b/.test(e));
  console.log(consoleErrors.length ? `console: ${consoleErrors.join(' | ')}` : 'console: clean');
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-validation: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
  await browser.contexts()[0]?.pages()[0]?.screenshot({ path: shot('verify-validation-error.png') }).catch(() => undefined);
} finally {
  await browser.close();
  runBackendScript(python, 'cleanup', [purge, '--accepted-findings', ...accepted, '--validation-runs', ...runs]);
  runBackendScript(python, 'cleanup', [purge, '--restore-confunfis', '--snapshot', ROWS_SNAPSHOT]);
  const rule = (await admin('GET', '/validation-rules')).find((r) => r.code === 'CF-018');
  if (rule.active !== ruleBefore.active || rule.severity !== ruleBefore.severity) {
    await admin('PATCH', '/validation-rules/CF-018', { version: rule.version, active: ruleBefore.active, severity: ruleBefore.severity });
    console.log('cleanup: CF-018 como estaba');
  }
}
process.exit(failed ? 1 : 0);
