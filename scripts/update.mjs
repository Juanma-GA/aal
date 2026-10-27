#!/usr/bin/env node
// npm run update  (E15) -- after a `git pull`, only what the pulled commits
// need:
//   - npm ci, when package-lock.json changed;
//   - pip install --require-hashes -r requirements-dev.lock.txt, when a
//     Python lockfile changed (`uv pip` if the virtualenv has no pip);
//   - alembic upgrade head, always (cheap, and it never hurts);
//   - npm run test:db:create, when there are new migrations;
//   - backend/scripts/refresh_findings.py, when the migrations or the validator's rules changed (E16);
//   - with --check (npm run update -- --check), npm run check:all at the end.
// Then a summary: what was done, what was not needed and why.
//
// "Changed" is against the last commit this script brought the machine up
// to, kept in .aal-update/last-head (ignored by git), or else against
// ORIG_HEAD (where the last pull started). With neither, everything runs.
// The stamp is only written when every step went well, so a failed run is
// repeated in full the next time.
//
// Plain Node, no shell: the same in PowerShell and Linux. npm runs as
// `node <npm-cli.js>` (npm_execpath, set by `npm run`), Python is the
// backend's (scripts/lib/backendPython.mjs). Exit code: 0 all well, 1 a step
// failed, 2 something is missing (git, the backend Python).
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { findBackendPython, pythonEnv, BACKEND_DIR } from './lib/backendPython.mjs';
import { rule, seconds } from './lib/checkReport.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const STAMP_DIR = path.join(ROOT, '.aal-update');
const STAMP = path.join(STAMP_DIR, 'last-head');
const withCheck = process.argv.includes('--check');
const done = [];
let failed = false;

function git(args) {
  const res = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8', windowsHide: true });
  if (res.error) return { ok: false, out: res.error.message };
  return { ok: res.status === 0, out: (res.stdout || '').trim() };
}

function run(label, command, args, cwd, { missingIs2 = false } = {}) {
  console.log(`\n▶ ${label}`);
  const started = Date.now();
  const res = spawnSync(command, args, { cwd, stdio: 'inherit', env: pythonEnv(), windowsHide: true });
  const ok = !res.error && res.status === 0;
  // check:all exits 2 when something of the environment is missing: not a failure, not "all checked".
  const missing = missingIs2 && !res.error && res.status === 2;
  done.push({ label, result: ok ? 'OK' : missing ? 'NO EJECUTADO' : 'FALLO', detail: res.error ? res.error.message : seconds(Date.now() - started) });
  if (!ok && !missing) failed = true;
  return ok;
}

function skip(label, why) {
  done.push({ label, result: 'no hacía falta', detail: why });
}

function npm(args) {
  // `npm run update` sets npm_execpath (npm-cli.js): no npm.cmd, no shell, on Windows too.
  const cli = process.env.npm_execpath;
  return cli && cli.endsWith('.js') ? [process.execPath, [cli, ...args]] : ['npm', args];
}

const head = git(['rev-parse', 'HEAD']);
if (!head.ok) {
  console.log(`update: no se puede leer git (${head.out}). ¿Está instalado y es un clon del repo?`);
  process.exit(2);
}
let base = null;
let baseFrom = null;
if (fs.existsSync(STAMP)) {
  const stamped = fs.readFileSync(STAMP, 'utf8').trim();
  if (stamped && git(['cat-file', '-e', `${stamped}^{commit}`]).ok) [base, baseFrom] = [stamped, 'el último npm run update'];
}
if (!base) {
  const orig = git(['rev-parse', '--verify', '--quiet', 'ORIG_HEAD']);
  if (orig.ok && orig.out) [base, baseFrom] = [orig.out, 'ORIG_HEAD (el último git pull)'];
}
const diff = base ? git(['diff', '--name-only', base, head.out]) : null;
// Without a list of what changed (no reference, or git diff failed), everything is done: never skipped by guess (HR7).
const changed = diff && diff.ok ? diff.out.split(/\r?\n/).filter(Boolean) : null;
const touched = (test) => changed === null || changed.some(test);
console.log(!base
  ? 'update: sin referencia anterior (primera vez): se hace todo.'
  : changed === null
    ? `update: git diff falló (${diff.out || 'sin detalle'}): se hace todo.`
    : `update: ${changed.length} ficheros cambiados desde ${baseFrom} (${base.slice(0, 7)} → ${head.out.slice(0, 7)}).`);

// 1. Frontend dependencies.
if (touched((f) => f === 'package-lock.json')) {
  const [cmd, args] = npm(['ci']);
  run('npm ci', cmd, args, ROOT);
} else skip('npm ci', 'package-lock.json no ha cambiado');

// 2. Backend dependencies, then the database.
const python = findBackendPython({ modules: ['alembic'] });
if (!python.python) {
  console.log(`update: no hay Python del backend (${python.reason}). Créalo como dice el README y repite.`);
  done.push({ label: 'backend', result: 'NO EJECUTADO', detail: python.reason });
} else {
  if (touched((f) => /^backend\/requirements(-dev)?\.lock\.txt$/.test(f))) {
    const lock = ['install', '--require-hashes', '-r', 'requirements-dev.lock.txt'];
    // A virtualenv made with `uv venv` has no pip: then `uv pip`, on that same Python.
    const hasPip = spawnSync(python.python, ['-m', 'pip', '--version'], { windowsHide: true }).status === 0;
    const hasUv = !hasPip && spawnSync('uv', ['--version'], { windowsHide: true }).status === 0;
    if (hasPip) run('pip install --require-hashes', python.python, ['-m', 'pip', ...lock], BACKEND_DIR);
    else if (hasUv) run('uv pip install --require-hashes', 'uv', ['pip', ...lock, '--python', python.python], BACKEND_DIR);
    else {
      done.push({ label: 'pip install', result: 'NO EJECUTADO', detail: 'el virtualenv no tiene pip ni hay uv' });
    }
  } else skip('pip install', 'los lockfiles de Python no han cambiado');
  run('alembic upgrade head', python.python, ['-m', 'alembic', 'upgrade', 'head'], BACKEND_DIR);
  if (touched((f) => f.startsWith('backend/alembic/versions/'))) {
    run('npm run test:db:create', process.execPath, [path.join('scripts', 'create-test-db.mjs')], ROOT);
  } else skip('npm run test:db:create', 'no hay migraciones nuevas');
  // The findings kept on the CONFUNFIS records follow the rules' code (E16).
  if (touched((f) => f.startsWith('backend/alembic/versions/') || f.startsWith('backend/app/validacion/'))) {
    run('refresh_findings.py', python.python, [path.join('scripts', 'refresh_findings.py')], BACKEND_DIR);
  } else skip('refresh_findings.py', 'ni migraciones ni reglas nuevas');
}

// 3. Optionally, the whole check.
if (withCheck && !failed) run('npm run check:all', process.execPath, [path.join('scripts', 'run-checks.mjs'), '--all'], ROOT, { missingIs2: true });
else if (!withCheck) skip('npm run check:all', 'sin --check');

console.log(`\n${rule()}\nnpm run update -- resumen`);
for (const d of done) console.log(`  ${d.label.padEnd(32)} ${d.result.padEnd(15)} ${d.detail}`);
const missing = done.some((d) => d.result === 'NO EJECUTADO');
if (!failed && !missing) {
  fs.mkdirSync(STAMP_DIR, { recursive: true });
  fs.writeFileSync(STAMP, `${head.out}\n`, 'utf8');
  console.log(`TODO AL DÍA (${head.out.slice(0, 7)})`);
}
process.exit(failed ? 1 : missing ? 2 : 0);
