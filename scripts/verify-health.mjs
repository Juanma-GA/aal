// E00: the home page shows the API's real state, in a real browser.
// The page is the login page (the status card is there for anyone).
//   1. With the backend up: "API conectada", the app's and the AACF's
//      version exactly as GET /api/version answers them, the database
//      operational and its migration; the logo loaded; the Inter font in
//      use; no request to another domain; no console error. Screenshot.
//   2. With /api/health answering the backend's sanitized 503
//      (database_unavailable): the page says the API is not available with
//      the translated sentence and the reference, and a retry button.
//      Screenshot.
//
// Needs the Vite dev server (BASE_URL, default http://localhost:5173) and
// uvicorn on 8000 running (CLAUDE.md, "Cómo levantar el entorno"); when the
// page is not reachable it says so and exits 2 (NOT RUN), not 1.
//
//   node scripts/verify-health.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));

function assert(cond, msg) {
  if (!cond) throw new Error('ASSERTION FAILED: ' + msg);
  console.log('OK:', msg);
}

async function reachable(url) {
  try {
    const res = await fetch(url);
    return res.ok;
  } catch {
    return false;
  }
}

if (!(await reachable(BASE_URL)) || !(await reachable(`${BASE_URL}/api/version`))) {
  console.log(`NOT RUN (environment): ${BASE_URL} or its /api is not reachable -- start uvicorn (port 8000) and Vite first.`);
  process.exit(2);
}
const expected = await (await fetch(`${BASE_URL}/api/version`)).json();

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const consoleErrors = [];
  const foreign = [];
  const origin = new URL(BASE_URL).origin;
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.protocol.startsWith('http') && u.origin !== origin) foreign.push(r.url());
  });

  // ── 1. Backend up ─────────────────────────────────────────────────────
  await page.goto(BASE_URL);
  const status = page.getByTestId('api-status');
  await status.waitFor();
  assert((await status.textContent()) === es.status.connected, `the page says "${es.status.connected}"`);
  assert((await page.getByTestId('app-version').textContent()) === expected.app, `app version ${expected.app}, as /api/version`);
  assert((await page.getByTestId('aacf-version').textContent()) === expected.aacf, `AACF version ${expected.aacf}, as /api/version`);
  assert((await page.getByTestId('database-status').textContent()) === es.status.databaseOk, 'database operational');
  const migration = await page.getByTestId('migration-status').textContent();
  assert(/al día/.test(migration), `migration shown up to date: "${migration}"`);
  assert((await page.locator('h1').textContent()) === es.app.title, 'header title from the locale');
  assert((await page.title()) === es.app.title, 'document title from the locale');
  const logo = page.getByTestId('brand-logo');
  assert(await logo.evaluate((img) => img.complete && img.naturalWidth > 0), 'logo loaded');
  assert((await logo.getAttribute('alt')) === es.app.logoAlt, 'logo alt text from the locale');
  const font = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
  assert(font.startsWith('Inter'), `body font is Inter (${font})`);
  assert(await page.evaluate(() => document.fonts.check('16px Inter')), 'Inter actually loaded');
  await page.screenshot({ path: shot('verify-health.png'), fullPage: true });
  console.log('screenshot:', shot('verify-health.png'));

  // ── 2. The backend's sanitized 503 ────────────────────────────────────
  await page.route('**/api/health', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: { code: 'database_unavailable', ref: 'abcd1234' } }),
    }),
  );
  await page.reload();
  await page.getByRole('alert').waitFor();
  assert((await status.textContent()) === es.status.disconnected, `the page says "${es.status.disconnected}"`);
  assert((await page.getByTestId('api-error').textContent()) === es.errors.database_unavailable, 'translated error sentence');
  assert((await page.getByRole('alert').textContent()).includes('abcd1234'), 'error reference shown');
  assert(await page.getByRole('button', { name: es.actions.retry }).isVisible(), 'retry button');
  await page.screenshot({ path: shot('verify-health-error.png'), fullPage: true });
  console.log('screenshot:', shot('verify-health-error.png'));
  await page.unroute('**/api/health');

  // The route above answers 503 on purpose, and without a session the
  // silent refresh answers 401: the browser logs both responses.
  const unexpected = consoleErrors.filter((e) => !/\b(503|401)\b/.test(e));
  assert(unexpected.length === 0, `no console errors${unexpected.length ? `: ${unexpected.join(' | ')}` : ''}`);
  assert(foreign.length === 0, `no request to another domain${foreign.length ? `: ${foreign.join(', ')}` : ''}`);
  console.log('verify-health: ALL OK');
} finally {
  await browser.close();
}
