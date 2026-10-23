// What the verify-* scripts share: the admin's API session (credentials
// from the environment, never arguments: D17) and the cleanup of what they
// created (backend/scripts/purge_verify_data.py).
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { BACKEND_DIR, findBackendPython, pythonEnv } from './backendPython.mjs';

export function notRun(reason) {
  console.log(`NOT RUN (environment): ${reason}`);
  process.exit(2);
}

/** The backend's Python (for the cleanup), or NOT RUN. */
export function backendPythonOrNotRun() {
  const found = findBackendPython({ modules: ['sqlalchemy', 'asyncpg'] });
  if (!found.python) notRun(found.reason);
  return found.python;
}

/** A backend script (from backend/) with the backend's Python; its exit
 *  code, and its output logged under `label`. */
export function runBackendScript(python, label, args) {
  const res = spawnSync(python, args, { cwd: BACKEND_DIR, env: pythonEnv(), encoding: 'utf8' });
  console.log(`${label}: ${(res.stdout || res.stderr || '').trim() || `exit ${res.status}`}`);
  return res.status;
}

export function purgeVerifyData(python, { users = [], materials = [], importJobs = [], catalogVersions = [] }) {
  const args = [path.join('scripts', 'purge_verify_data.py')];
  if (users.length) args.push('--users', ...users);
  if (materials.length) args.push('--materials', ...materials);
  if (importJobs.length) args.push('--import-jobs', ...importJobs);
  if (catalogVersions.length) args.push('--catalog-versions', ...catalogVersions);
  runBackendScript(python, 'cleanup', args);
}

/** A tiny API client signed in as `email` (no browser). */
export async function apiSession(baseUrl, email, password) {
  const res = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`login as ${email} answered ${res.status}`);
  const { access_token: token } = await res.json();
  return async (method, apiPath, body) => {
    const r = await fetch(`${baseUrl}/api${apiPath}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${method} ${apiPath} answered ${r.status}: ${await r.text()}`);
    return r.status === 204 ? null : r.json();
  };
}
