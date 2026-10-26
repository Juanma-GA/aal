// E02: the app's shell, the PALI catalog and the material's Panel, in a
// real browser.
//   1. The development analyst signs in and lands on their material's Panel
//      (/materiales/:id).
//   2. The Panel shows real data: the CUF, the role, the team, the module
//      counts (the same as /api/modules) and recent activity.
//   3. Three sidebar groups (Base común, PAAL, PRAMT) open their module
//      cards; (E13) "Configuración funcional física" opens the CONFUNFIS and
//      the card of "Tabla de partes" shows RF-02, its dependency with its
//      state and the "planned" notice, with breadcrumbs and the tab title.
//   4. The URL of a material the analyst is not in -> the humanized 404.
//   5. The admin changes a module (FTA) to "en desarrollo" in Ajustes ->
//      Módulos.
//   6. The analyst sees the new state in the sidebar.
//   7. Phone width: the sidebar is a side panel opened from the header.
//   (E12) The sidebar's edge is dragged wider, Ctrl+B folds it to its icons
//   (with tooltips) and its button at the foot unfolds it, it moves to the
//   right and back; width and folding survive a reload.
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
// The analyst has several materials since E11: the check starts on the
// development one (their preferences are given back at the end).
const sidebarLimits = (await analyst('GET', '/me/ui-settings')).sidebar_width;
await analyst('PUT', '/me/ui-preferences', {
  sidebar_collapsed_groups: [],
  active_material_id: devMaterial.id,
  sidebar_folded: false,
  sidebar_width: sidebarLimits.default,
  sidebar_side: 'left',
});

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

  // ── 3. Three groups of the sidebar, and the Tabla de partes card ───────
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
  // (E13) So does the CONFUNFIS, inside the material.
  await page.getByTestId('sidebar-module-confunfis').click();
  await page.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/confunfis`);
  await page.getByTestId('confunfis-page').waitFor();
  assert(true, 'base: "Configuración funcional física" opens the CONFUNFIS of the material');
  await page.getByTestId('sidebar-module-tabla-partes').click();
  await page.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/modulos/tabla-partes`);
  await page.locator('main h2', { hasText: 'Tabla de partes' }).waitFor();
  assert((await page.getByTestId('module-requirements').textContent()).includes('RF-02'), 'the card shows RF-02');
  const deps = await page.getByTestId('module-depends-on').textContent();
  assert(deps.includes('Configuración funcional física'), 'the card shows its dependency');
  // The CONFUNFIS is available since E13.
  const states = page.getByTestId('module-depends-on');
  assert((await states.getByRole('img', { name: es.modules.status.disponible }).count()) === 1, 'the dependency shows its state');
  assert((await page.getByTestId('module-planned').textContent()).includes(es.modules.planned), 'the planned notice');
  assert((await page.getByTestId('module-card').getByRole('button').count()) === 0, 'no button on a planned module');
  const crumbs = await page.getByRole('navigation', { name: es.nav.breadcrumb }).textContent();
  assert(crumbs.includes(MATERIAL_NAME) && crumbs.includes('Base común') && crumbs.includes('Tabla de partes'), 'breadcrumbs material › group › module');
  assert((await page.title()).startsWith('Tabla de partes'), 'tab title of the card');
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

  // The sidebar (E12): dragged wider, folded with Ctrl+B, on the right.
  const saved = () => page.waitForResponse((r) => r.url().endsWith('/api/me/ui-preferences') && r.request().method() === 'PUT' && r.ok());
  const sidebarWidth = () => page.locator('[data-slot="sidebar-container"]').evaluate((el) => Math.round(el.getBoundingClientRect().width));
  assert((await sidebarWidth()) === sidebarLimits.default, `the sidebar starts at ${sidebarLimits.default}px`);
  const edge = await page.getByTestId('sidebar-resizer').boundingBox();
  const startX = edge.x + edge.width / 2;
  await page.mouse.move(startX, edge.y + 200);
  await page.mouse.down();
  await page.mouse.move(startX + 60, edge.y + 200, { steps: 5 });
  await Promise.all([saved(), page.mouse.up()]);
  await page.waitForTimeout(300); // its width transition
  const wider = await sidebarWidth();
  assert(Math.abs(wider - (sidebarLimits.default + 60)) <= 2, `dragging the edge widens it (${wider}px)`);
  await Promise.all([saved(), page.keyboard.press('Control+b')]);
  await page.waitForTimeout(300);
  assert((await page.getByTestId('app-sidebar').getAttribute('data-folded')) === '', 'Ctrl+B folds the sidebar');
  assert((await sidebarWidth()) < 80, 'folded, only its icons are left');
  await page.getByTestId(`sidebar-module-${MODULE}`).hover();
  await page.getByRole('tooltip').waitFor();
  await page.reload();
  await page.getByTestId('module-card').waitFor();
  await page.waitForTimeout(300);
  assert((await page.getByTestId('app-sidebar').getAttribute('data-folded')) === '', 'folded after a reload');
  await Promise.all([saved(), page.getByTestId('sidebar-fold').click()]);
  await page.waitForTimeout(300);
  assert((await sidebarWidth()) === wider, 'the button at the foot unfolds it, with the width kept');
  await Promise.all([saved(), page.getByTestId('sidebar-side').click()]);
  const box = await page.locator('[data-slot="sidebar-container"]').boundingBox();
  assert(box.x + box.width >= (page.viewportSize()?.width ?? 0) - 2, 'the sidebar moves to the right');
  await page.screenshot({ path: shot('verify-navigation-2b-sidebar-right.png') });
  await Promise.all([saved(), page.getByTestId('sidebar-side').click()]);

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
  await mobile.getByRole('dialog').getByTestId('sidebar-module-tabla-partes').click();
  await mobile.waitForURL(`${BASE_URL}/materiales/${devMaterial.id}/modulos/tabla-partes`);
  await mobile.getByRole('dialog').waitFor({ state: 'hidden', timeout: 5000 });
  assert(true, 'phone: choosing a module closes the panel');
  await mobile.locator('main h2', { hasText: 'Tabla de partes' }).waitFor();
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
      sidebar_folded: analystPreferences.sidebar_folded ?? false,
      sidebar_width: analystPreferences.sidebar_width ?? sidebarLimits.default,
      sidebar_side: analystPreferences.sidebar_side ?? 'left',
    });
    console.log("cleanup: the analyst's preferences given back");
  } catch (err) {
    console.log(`cleanup: could not give the analyst's preferences back: ${err.message}`);
  }
  purgeVerifyData(python, { materials: [FOREIGN_NAME] });
}
process.exit(failed ? 1 : 0);
