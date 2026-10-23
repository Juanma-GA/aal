// E02: the app's shell, the PALI catalog and the material's Panel, in a
// real browser.
//   1. The development analyst signs in and lands on their material's Panel
//      (/materiales/:id).
//   2. The Panel shows real data: the CUF, the role, the team, the module
//      counts (the same as /api/modules) and recent activity.
//   3. Three sidebar groups (Base común, PAAL, PRAMT) open their module
//      cards; the card of "Configuración funcional física" shows RF-02, its
//      dependencies with their state, who uses it and the "planned" notice,
//      with breadcrumbs and the tab title.
//   4. The URL of a material the analyst is not in -> the humanized 404.
//   5. The admin changes a module (FTA) to "en desarrollo" in Ajustes ->
//      Módulos.
//   6. The analyst sees the new state in the sidebar.
//   7. Phone width: the sidebar is a side panel opened from the header.
// Leaves the database as it was: the foreign material
// ("[verify] Material ajeno") is removed (backend/scripts/purge_verify_data.py)
// FTA is set back to "planificado" and the analyst's interface preferences
// are given back; only audit rows stay.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py and the data of seed_dev_data.py.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD, DEV_ANALISTA_PASSWORD
//   (VERIFY_ANALISTA_EMAIL, default analista.dev@aal-dev.es)
// Without them, or without the servers, it says so and exits 2 (NOT RUN).
//
//   node scripts/verify-navigation.mjs
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
const MATERIAL_NAME = process.env.VERIFY_MATERIAL_NAME || 'Material de desarrollo (sintético)';
const FOREIGN_NAME = '[verify] Material ajeno';
const MODULE = 'fta';
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));

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
const groups = await admin('GET', '/modules');
const all = groups.flatMap((g) => g.modules);
const devMaterial = (await admin('GET', '/materials')).find((m) => m.name === MATERIAL_NAME);
if (!devMaterial) notRun(`no material "${MATERIAL_NAME}" -- run backend/scripts/seed_dev_data.py.`);
const foreign = await admin('POST', '/materials', { name: FOREIGN_NAME, description: 'Creado y borrado por verify-navigation.' });
// The analyst's interface preferences, given back at the end, and a known
// start: no folded group.
const analyst = await apiSession(BASE_URL, ANALYST_EMAIL, ANALYST_PASSWORD);
const analystPreferences = (await analyst('GET', '/auth/me')).ui_preferences;
await analyst('PUT', '/me/ui-preferences', { sidebar_collapsed_groups: [] });

async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const analystContext = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await analystContext.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. Lands on the Panel of their material ────────────────────────────
  await signIn(page, ANALYST_EMAIL, ANALYST_PASSWORD);
  await page.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}`);
  assert(true, 'the analyst lands on /materiales/:id of their material');

  // ── 2. Real data on the Panel ──────────────────────────────────────────
  const card = page.getByTestId('active-material');
  await card.waitFor();
  assert((await card.textContent()).includes(MATERIAL_NAME), 'the Panel shows the CUF');
  assert((await page.getByTestId('panel-role').textContent()) === es.roles.analista, 'the Panel shows the role Analista');
  const team = page.getByTestId('panel-team');
  await team.getByText('Revisor de desarrollo').waitFor();
  assert((await team.textContent()).includes('Observador de desarrollo'), 'the team lists the members');
  for (const status of ['disponible', 'en_desarrollo', 'planificado']) {
    const expected = all.filter((m) => m.status === status).length;
    const tile = await page.getByTestId(`panel-count-${status}`).textContent();
    assert(tile.includes(String(expected)), `${expected} modules ${status}, as /api/modules`);
  }
  const activity = page.getByTestId('panel-activity');
  await activity.locator('li').first().waitFor();
  assert((await activity.locator('li').count()) > 0, 'recent activity is listed');
  assert((await page.title()).startsWith(es.panel.title), 'tab title of the Panel');
  await page.screenshot({ path: shot('verify-navigation-1-panel.png'), fullPage: true });

  // ── 3. Three groups of the sidebar, and the CONFUNFIS card ─────────────
  for (const [group, module] of [['base', 'tabla-partes'], ['paal', 'candidatos'], ['pramt', 'amfec']]) {
    await page.getByTestId(`sidebar-group-${group}`).waitFor();
    await page.getByTestId(`sidebar-module-${module}`).click();
    await page.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/modulos/${module}`);
    const name = all.find((m) => m.code === module).name;
    await page.locator('main h2', { hasText: name }).waitFor();
    assert((await page.getByTestId('module-card').count()) === 1, `${group}: the card of ${name}`);
  }
  // An available module opens its own page: the common SNS catalog (E10),
  // outside the material.
  await page.getByTestId('sidebar-module-catalogo-normalizado').click();
  await page.waitForURL(`${BASE_URL}/configuracion-funcional`);
  await page.getByTestId('catalog-page').waitFor();
  assert(true, 'base: "Configuración funcional normalizada" opens the common catalog');
  await page.getByTestId('sidebar-module-confunfis').click();
  await page.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/modulos/confunfis`);
  await page.locator('main h2', { hasText: 'Configuración funcional física' }).waitFor();
  assert((await page.getByTestId('module-requirements').textContent()).includes('RF-02'), 'the card shows RF-02');
  const deps = await page.getByTestId('module-depends-on').textContent();
  assert(deps.includes('Materiales / CUF') && deps.includes('Artículos — datos básicos'), 'the card shows its dependencies');
  assert((await page.getByTestId('module-depends-on').getByRole('img', { name: es.modules.status.en_desarrollo }).count()) === 1, 'each dependency shows its state');
  assert((await page.getByTestId('module-used-by').textContent()).includes('Tabla de partes'), 'the card shows who uses it');
  assert((await page.getByTestId('module-planned').textContent()).includes(es.modules.planned), 'the planned notice');
  assert((await page.getByTestId('module-card').getByRole('button').count()) === 0, 'no button on a planned module');
  const crumbs = await page.getByRole('navigation', { name: es.nav.breadcrumb }).textContent();
  assert(crumbs.includes(MATERIAL_NAME) && crumbs.includes('Base común') && crumbs.includes('Configuración funcional física'), 'breadcrumbs material › group › module');
  assert((await page.title()).startsWith('Configuración funcional física'), 'tab title of the card');
  await page.screenshot({ path: shot('verify-navigation-2-card.png'), fullPage: true });

  // Folding a group is kept on the server: it survives a reload.
  await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/me/ui-preferences') && r.ok()),
    page.getByTestId('sidebar-group-pman').getByRole('button').first().click(),
  ]);
  await page.reload();
  await page.getByTestId('module-card').waitFor();
  assert((await page.getByTestId('sidebar-module-plan-mantenimiento').count()) === 0, 'a folded group stays folded after a reload');
  await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/me/ui-preferences') && r.ok()),
    page.getByTestId('sidebar-group-pman').getByRole('button').first().click(),
  ]);

  // ── 4. A material they are not in ──────────────────────────────────────
  await page.goto(`${BASE_URL}/materiales/${foreign.id}`);
  await page.getByTestId('not-found').waitFor();
  assert((await page.getByTestId('not-found').textContent()).includes(es.notFound.material), 'a foreign material is the humanized 404');
  await page.goto(`${BASE_URL}/materiales/${devMaterial.id}`);
  await page.getByTestId('active-material').waitFor();

  // ── 5. The admin changes a module in Ajustes -> Módulos ────────────────
  const adminContext = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const adminPage = await adminContext.newPage();
  await signIn(adminPage, ADMIN_EMAIL, ADMIN_PASSWORD);
  await adminPage.getByTestId('settings-link').waitFor();
  await adminPage.goto(`${BASE_URL}/ajustes/modulos`);
  const row = adminPage.getByTestId(`module-row-${MODULE}`);
  await row.getByRole('button', { name: es.settings.modules.change }).click();
  await adminPage.getByTestId('module-status-select').click();
  await adminPage.getByRole('option', { name: es.modules.status.en_desarrollo }).click();
  await Promise.all([
    adminPage.waitForResponse((r) => r.url().endsWith(`/api/modules/${MODULE}`) && r.request().method() === 'PATCH' && r.ok()),
    adminPage.getByTestId('module-save').click(),
  ]);
  assert((await row.textContent()).includes(es.modules.status.en_desarrollo), 'Ajustes -> Módulos shows FTA en desarrollo');
  await adminPage.screenshot({ path: shot('verify-navigation-3-settings-modules.png'), fullPage: true });

  // ── 6. The analyst sees it ─────────────────────────────────────────────
  await page.reload();
  const link = page.getByTestId(`sidebar-module-${MODULE}`);
  await link.waitFor();
  assert((await link.getAttribute('data-status')) === 'en_desarrollo', 'the analyst sees FTA en desarrollo in the sidebar');
  assert((await link.getByRole('img', { name: es.modules.status.en_desarrollo }).count()) === 1, 'with the state icon and its text');

  // ── 7. Phone width: the sidebar is a side panel ────────────────────────
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const mobile = await phone.newPage();
  await signIn(mobile, ANALYST_EMAIL, ANALYST_PASSWORD);
  await mobile.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}`);
  await mobile.getByTestId('active-material').waitFor();
  assert(!(await mobile.getByTestId('sidebar-group-base').isVisible()), 'phone: the sidebar is hidden');
  await mobile.screenshot({ path: shot('verify-navigation-4-mobile-panel.png'), fullPage: true });
  await mobile.getByTestId('sidebar-trigger').click();
  await mobile.getByRole('dialog').getByTestId('sidebar-group-base').waitFor();
  // The panel slides in: wait until it stands still at the left edge.
  await mobile.waitForFunction(() => {
    const box = document.querySelector('[role="dialog"]')?.getBoundingClientRect();
    return box && box.left === 0 && box.width > 0;
  });
  await mobile.waitForTimeout(400);
  assert(true, 'phone: the menu opens as a side panel');
  await mobile.screenshot({ path: shot('verify-navigation-5-mobile-menu.png') });
  await mobile.getByRole('dialog').getByTestId('sidebar-module-confunfis').click();
  await mobile.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/modulos/confunfis`);
  await mobile.getByRole('dialog').waitFor({ state: 'hidden', timeout: 5000 });
  assert(true, 'phone: choosing a module closes the panel');
  await mobile.locator('main h2', { hasText: 'Configuración funcional física' }).waitFor();
  await mobile.screenshot({ path: shot('verify-navigation-6-mobile-card.png'), fullPage: true });

  const unexpected = consoleErrors.filter((e) => !/\b(401|404)\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-navigation: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  try {
    const current = (await admin('GET', `/modules/${MODULE}`)).version;
    await admin('PATCH', `/modules/${MODULE}`, { version: current, status: 'planificado', route: null });
    console.log(`cleanup: ${MODULE} back to planificado`);
  } catch (err) {
    console.log(`cleanup: could not set ${MODULE} back: ${err.message}`);
  }
  try {
    await analyst('PUT', '/me/ui-preferences', {
      active_material_id: analystPreferences.active_material_id ?? null,
      sidebar_collapsed_groups: analystPreferences.sidebar_collapsed_groups ?? [],
    });
    console.log("cleanup: the analyst's preferences given back");
  } catch (err) {
    console.log(`cleanup: could not give the analyst's preferences back: ${err.message}`);
  }
  purgeVerifyData(python, { materials: [FOREIGN_NAME] });
}
process.exit(failed ? 1 : 0);
