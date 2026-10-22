// E01: users, roles per material and Settings, in a real browser.
//   1. The admin signs in and creates a user, who gets a temporary password
//      (shown once) and a pending password change.
//   2. The admin gives that user the Observador role on the development
//      material (backend/scripts/seed_dev_data.py).
//   3. The user signs in with the temporary password, is sent to change it,
//      lands on their material's Panel (/materiales/:id) with the badge
//      "Observador"; they see no edit action and no Settings (and /ajustes
//      sends them back to their material).
//   4. The admin sees all of it in Settings -> Auditoría.
// No token in localStorage / sessionStorage at any point; the refresh
// cookie is HttpOnly. The user is removed at the end
// (backend/scripts/purge_verify_data.py), so the database stays as it was
// -- but for the audit rows, which are append-only.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running,
// the admin of create_admin_user.py and the data of seed_dev_data.py. The
// admin's credentials come from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD
// Without them, or without the servers, it says so and exits 2 (NOT RUN).
//
//   node scripts/verify-auth-settings.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';
import { backendPythonOrNotRun, notRun, purgeVerifyData } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const ADMIN_EMAIL = process.env.VERIFY_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.VERIFY_ADMIN_PASSWORD;
const MATERIAL_NAME = process.env.VERIFY_MATERIAL_NAME || 'Material de desarrollo (sintético)';
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));
const USER_EMAIL = `observador-${Date.now()}@verify.aal-dev.es`;
const USER_NAME = 'Observador de verificación';
const NEW_PASSWORD = `Verificacion-${Date.now()}-x`;

function assert(cond, msg) {
  if (!cond) throw new Error('ASSERTION FAILED: ' + msg);
  console.log('OK:', msg);
}

if (!ADMIN_EMAIL || !ADMIN_PASSWORD) notRun('set VERIFY_ADMIN_EMAIL and VERIFY_ADMIN_PASSWORD (the admin of create_admin_user.py).');
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const purge = () => purgeVerifyData(python, { users: [USER_EMAIL] });

async function noBrowserStorage(page, when) {
  const stored = await page.evaluate(() => ({ local: window.localStorage.length, session: window.sessionStorage.length }));
  assert(stored.local === 0 && stored.session === 0, `nothing in localStorage / sessionStorage (${when})`);
}

async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(email);
  await page.getByLabel(es.auth.password, { exact: true }).fill(password);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/login')), page.getByRole('button', { name: es.actions.signIn }).click()]);
}

async function signOut(page) {
  await page.getByTestId('user-menu').click();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/auth/logout')), page.getByTestId('sign-out').click()]);
  await page.waitForURL('**/login');
}

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

  // ── 1. The admin creates the user ───────────────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByTestId('settings-link').waitFor();
  assert(true, 'the admin is in and sees Settings');
  const cookies = await context.cookies();
  const refresh = cookies.find((c) => c.name === 'aal_refresh');
  assert(refresh && refresh.httpOnly && refresh.sameSite === 'Strict' && refresh.path === '/api/auth', 'refresh cookie: HttpOnly, SameSite=Strict, Path=/api/auth');
  assert(!cookies.some((c) => /access/i.test(c.name)), 'no access token in a cookie');
  await noBrowserStorage(page, 'admin signed in');

  await page.goto(`${BASE_URL}/ajustes/usuarios`);
  await page.getByTestId('new-user').click();
  const form = page.getByTestId('user-form');
  await form.getByLabel(es.settings.users.email).fill(USER_EMAIL);
  await form.getByLabel(es.settings.users.name).fill(USER_NAME);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/users') && r.request().method() === 'POST'), form.getByRole('button', { name: es.actions.create }).click()]);
  const temporary = (await page.getByTestId('temporary-password').textContent()).trim();
  assert(temporary.length >= 12, 'the temporary password is shown');
  await page.screenshot({ path: shot('verify-auth-1-temporary-password.png') });
  await page.getByRole('dialog').getByRole('button', { name: es.actions.close }).last().click();
  const row = page.getByTestId(`user-row-${USER_EMAIL}`);
  await row.waitFor();
  assert((await row.textContent()).includes(es.settings.users.pendingChange), 'the new user has a pending password change');

  // ── 2. Observador on the development material ──────────────────────────
  await page.goto(`${BASE_URL}/ajustes/materiales`);
  await page.getByTestId(`members-${MATERIAL_NAME}`).click();
  await page.getByTestId('member-user').click();
  await page.getByRole('option', { name: new RegExp(USER_EMAIL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
  await page.getByTestId('member-role').click();
  await page.getByRole('option', { name: es.roles.observador }).click();
  await Promise.all([page.waitForResponse((r) => r.url().includes('/members/') && r.request().method() === 'PUT' && r.ok()), page.getByTestId('add-member').click()]);
  await page.getByTestId(`member-${USER_EMAIL}`).waitFor();
  assert(true, 'the user is a member of the material');
  await page.screenshot({ path: shot('verify-auth-2-members.png') });
  await page.keyboard.press('Escape');
  await signOut(page);

  // ── 3. The user: forced change, the material, read-only ────────────────
  await signIn(page, USER_EMAIL, temporary);
  await page.waitForURL('**/cambiar-contrasena');
  assert(true, 'the user is sent to change the password');
  await page.getByTestId('change-password-form').getByLabel(es.auth.currentPassword).fill(temporary);
  await page.getByLabel(es.auth.newPassword, { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel(es.auth.repeatPassword).fill(NEW_PASSWORD);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/me/password') && r.ok()), page.getByRole('button', { name: es.actions.changePassword }).click()]);
  // "/" takes them to their only material's Panel, which becomes their
  // active material (E02).
  await page.waitForURL(/\/materiales\/[0-9a-f-]{36}$/);
  await page.waitForResponse((r) => r.url().endsWith('/api/me/ui-preferences') && r.ok());
  assert((await page.getByTestId('material-selector').textContent()).includes(MATERIAL_NAME), 'the header selector shows the material');
  await page.getByTestId('active-material').waitFor();
  assert((await page.getByTestId('material-role').textContent()) === es.roles.observador, 'the header badge says Observador');
  const permissions = await page.getByTestId('material-permissions').textContent();
  assert(!/Editar|Aprobar|Enviar|Ejecutar/.test(permissions), 'the observer has no edit, approve, send or run permission');
  assert((await page.getByTestId('settings-link').count()) === 0, 'no Settings link');
  assert((await page.getByRole('button', { name: es.actions.edit }).count()) === 0, 'no edit button');
  assert((await page.getByTestId('panel-role').textContent()) === es.roles.observador, 'the Panel says Observador too');
  await noBrowserStorage(page, 'observer signed in');
  await page.screenshot({ path: shot('verify-auth-3-observer.png'), fullPage: true });
  await page.goto(`${BASE_URL}/ajustes/usuarios`);
  await page.waitForURL(/\/materiales\/[0-9a-f-]{36}$/);
  assert(true, '/ajustes sends the observer to their material');
  // The choice is on the server: a reload keeps it (the session comes back
  // from the cookie, the material from ui_preferences).
  await page.reload();
  await page.getByTestId('active-material').waitFor();
  assert((await page.getByTestId('material-role').textContent()) === es.roles.observador, 'after a reload: same material, same badge');
  await signOut(page);

  // ── 4. The admin sees it in Auditoría ──────────────────────────────────
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByTestId('settings-link').waitFor();
  await page.goto(`${BASE_URL}/ajustes/auditoria`);
  const table = page.getByTestId('audit-table');
  await table.waitFor();
  const text = await table.textContent();
  for (const action of ['user.created', 'material_role.assigned', 'user.password_changed', 'user.ui_preferences_updated', 'auth.login']) {
    assert(text.includes(es.audit.actions[action]), `Auditoría shows "${es.audit.actions[action]}"`);
  }
  assert(text.includes(USER_EMAIL), 'Auditoría shows the user');
  await page.getByRole('button', { name: es.audit.actions['material_role.assigned'] }).first().click();
  const detail = await page.getByTestId('audit-detail').textContent();
  assert(detail.includes(USER_EMAIL) && detail.includes('observador'), 'the detail shows who got which role');
  assert(!detail.includes(temporary) && !text.includes(temporary), 'no password in Auditoría');
  await page.screenshot({ path: shot('verify-auth-4-audit.png'), fullPage: true });

  const unexpected = consoleErrors.filter((e) => !/\b401\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  console.log('verify-auth-settings: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  purge();
}
process.exit(failed ? 1 : 0);
