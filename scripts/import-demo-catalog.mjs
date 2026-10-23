// Imports demo/CONF_FUN_DEMO.xlsx as a catalog version through the API (the
// same two phases as the ImportWizard), unless the active version is
// already it. For the CI before verify-materials, and for a fresh database.
// Credentials from the environment, never arguments (D17):
//   VERIFY_ADMIN_EMAIL, VERIFY_ADMIN_PASSWORD   (BASE_URL, default
//   http://localhost:5173). Without them or the servers: exit 2 (NOT RUN).
//
//   node scripts/import-demo-catalog.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { notRun } from './lib/verifyData.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const FILE = path.join(ROOT, 'demo', 'CONF_FUN_DEMO.xlsx');
const POLL_MS = 500;

if (!process.env.VERIFY_ADMIN_EMAIL || !process.env.VERIFY_ADMIN_PASSWORD) notRun('set VERIFY_ADMIN_EMAIL and VERIFY_ADMIN_PASSWORD.');
let login;
try {
  login = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: process.env.VERIFY_ADMIN_EMAIL, password: process.env.VERIFY_ADMIN_PASSWORD }),
  });
} catch {
  notRun(`${BASE_URL} is not reachable -- start uvicorn (port 8000) and Vite first.`);
}
if (!login.ok) notRun(`the admin's login answered ${login.status}.`);
const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
const call = async (method, apiPath, body) => {
  const res = await fetch(`${BASE_URL}/api${apiPath}`, { method, headers, body });
  if (!res.ok) throw new Error(`${method} ${apiPath} answered ${res.status}: ${await res.text()}`);
  return res.json();
};

const active = (await call('GET', '/catalog/versions')).find((v) => v.is_active);
if (active?.label === 'CONF_FUN_DEMO') {
  console.log(`import-demo-catalog: version ${active.number} (CONF_FUN_DEMO) is already the active one`);
  process.exit(0);
}
const form = new FormData();
form.append('file', new Blob([fs.readFileSync(FILE)]), 'CONF_FUN_DEMO.xlsx');
let job = await call('POST', '/catalog/import', form);
while (job.status === 'analyzing') {
  await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  job = await call('GET', `/import-jobs/${job.id}`);
}
if (job.status !== 'analyzed') {
  console.error(`import-demo-catalog: the analysis ended ${job.status} (${job.error_code})`);
  process.exit(1);
}
await call('POST', `/import-jobs/${job.id}/apply`);
console.log(`import-demo-catalog: imported (${job.counts.rows} rows, ${job.counts.sns} SNS)`);
