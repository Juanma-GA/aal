// E13: the articles grid with 2 000 synthetic articles, in a real browser,
// measured with the Event Timing API (from the key or click to the next
// paint): typing in a cell answers in under ARTICLES_PERF_KEY_MS (100 ms)
// and "Aplicar a la selección" on 200 rows in under ARTICLES_PERF_APPLY_MS
// (1 000 ms). Fails when either is exceeded.
// Leaves the database as it was: the articles are saved before and put back
// after (backend/scripts/purge_verify_data.py --save-articles /
// --restore-articles), which removes the synthetic ones.
//
// Needs Vite (BASE_URL, default http://localhost:5173) and uvicorn running
// and the data of seed_dev_data.py. Credentials from the environment, never
// arguments (D17): DEV_ANALISTA_PASSWORD (VERIFY_ANALISTA_EMAIL, default
// analista.dev@aal-dev.es). Without them, or without the servers, exits 2.
//
//   node scripts/verify-articles-perf.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { shot } from './lib/shots.mjs';
import { readTextFile } from './lib/textFile.mjs';
import { backendPythonOrNotRun, notRun, runBackendScript } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH;
const ANALYST_EMAIL = process.env.VERIFY_ANALISTA_EMAIL || 'analista.dev@aal-dev.es';
const ANALYST_PASSWORD = process.env.DEV_ANALISTA_PASSWORD;
const COUNT = 2000;
const KEY_MS = Number(process.env.ARTICLES_PERF_KEY_MS || 100);
const APPLY_MS = Number(process.env.ARTICLES_PERF_APPLY_MS || 1000);
const SNAPSHOT = shot(`verify-articles-perf-${Date.now()}.json`);
const es = JSON.parse(readTextFile(path.join(ROOT, 'src', 'i18n', 'locales', 'es.json')));

function assert(cond, msg) {
  if (!cond) throw new Error('ASSERTION FAILED: ' + msg);
  console.log('OK:', msg);
}

if (!ANALYST_PASSWORD) notRun('set DEV_ANALISTA_PASSWORD (seed_dev_data.py).');
try {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) notRun(`${BASE_URL}/api/health answered ${res.status}.`);
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
const python = backendPythonOrNotRun();
const purge = path.join('scripts', 'purge_verify_data.py');
if (runBackendScript(python, 'save the articles', [purge, '--save-articles', '--snapshot', SNAPSHOT]) !== 0) notRun('could not save the articles.');

const browser = await chromium.launch(CHROMIUM_PATH ? { executablePath: CHROMIUM_PATH } : {});
let failed = false;
try {
  if (runBackendScript(python, 'synthetic articles', [path.join('scripts', 'seed_synthetic_articles.py'), String(COUNT)]) !== 0) throw new Error('could not create the synthetic articles');
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(es.auth.email).fill(ANALYST_EMAIL);
  await page.getByLabel(es.auth.password, { exact: true }).fill(ANALYST_PASSWORD);
  await page.getByRole('button', { name: es.actions.signIn }).click();
  await page.getByTestId('user-menu').waitFor();
  await page.goto(`${BASE_URL}/articulos`);
  await page.getByTestId('articles-total').filter({ hasText: /\d{4}/ }).waitFor();
  await page.getByTestId('articles-grid-toggle').click();
  await page.getByTestId('article-grid').waitFor();
  // Every interaction from now on, from its input to the next paint.
  await page.evaluate(() => {
    window.__events = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__events.push({ name: e.name, duration: e.duration });
    }).observe({ type: 'event', durationThreshold: 16, buffered: false });
  });
  const longest = async (names) => {
    await page.waitForTimeout(300); // the observer reports after the paint
    const events = await page.evaluate(() => window.__events.splice(0));
    return Math.max(0, ...events.filter((e) => names.includes(e.name)).map((e) => e.duration));
  };

  // Typing in a numeric cell (Precio estándar) of the first row.
  const cell = page.getByTestId('article-grid').locator('input[data-field="imEstdArt"]').first();
  await cell.click();
  await longest(['pointerdown', 'pointerup', 'click']);
  await page.keyboard.type('12345', { delay: 50 });
  const typing = await longest(['keydown', 'keypress', 'keyup', 'input', 'beforeinput']);
  assert(typing < KEY_MS, `typing in a cell answers in ${Math.round(typing)} ms (< ${KEY_MS})`);

  // Select 200 rows and apply a value to them.
  await page.getByTestId('grid-select-all').click();
  await page.getByTestId('bulk-apply').filter({ hasText: '200' }).waitFor();
  await longest(['pointerdown', 'pointerup', 'click']);
  await page.getByTestId('bulk-apply').click();
  await page.getByTestId('grid-save').filter({ hasText: '200' }).waitFor();
  const applying = await longest(['pointerdown', 'pointerup', 'click']);
  assert(applying < APPLY_MS, `"Aplicar a la selección" on 200 rows in ${Math.round(applying)} ms (< ${APPLY_MS})`);
  await page.screenshot({ path: shot('verify-articles-perf.png') });
  console.log('verify-articles-perf: ALL OK');
} catch (err) {
  failed = true;
  console.error(err.message);
} finally {
  await browser.close();
  runBackendScript(python, 'cleanup', [purge, '--restore-articles', '--snapshot', SNAPSHOT]);
}
process.exit(failed ? 1 : 0);
