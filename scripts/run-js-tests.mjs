#!/usr/bin/env node
// npm run test:js -- every scripts/test-*.mjs, one by one (adapted from
// brdp-manager).
//
// One line per file (name, result, time) and a summary at the end. Exit
// code: 0 if all pass; 1 if any fails or hangs.
//
// A new scripts/test-*.mjs is picked up on its own: the list is read from
// the folder on every run.
//
// Options:
//   --timeout <seconds>   per file (default 180, or $JS_TEST_TIMEOUT_SECONDS).
//                         A file that runs longer is killed and reported --
//                         a watchdog for a hung test, far above what any
//                         file needs (Windows laptops run 4-5 times slower).
//   <text> ...            only the files whose name contains one of them.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { duration, rule, runProcess, seconds, tail } from './lib/checkReport.mjs';

const SCRIPTS = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(SCRIPTS);

function parseArgs(argv) {
  let timeout = Number(process.env.JS_TEST_TIMEOUT_SECONDS) || 180;
  const filters = [];
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--timeout') {
      timeout = Number(argv[i + 1]);
      i += 1;
      if (!(timeout > 0)) {
        console.error('--timeout needs a number of seconds greater than 0');
        process.exit(2);
      }
    } else filters.push(argv[i]);
  }
  return { timeoutMs: timeout * 1000, filters };
}

const { timeoutMs, filters } = parseArgs(process.argv.slice(2));
const files = fs
  .readdirSync(SCRIPTS)
  .filter((f) => /^test-.*\.mjs$/.test(f))
  .filter((f) => !filters.length || filters.some((t) => f.includes(t)))
  .sort();

if (!files.length) {
  console.error(filters.length ? `No scripts/test-*.mjs matches: ${filters.join(', ')}` : 'No scripts/test-*.mjs found.');
  process.exit(2);
}

console.log(`JS tests: ${files.length} files (scripts/test-*.mjs), up to ${seconds(timeoutMs)} each`);
const width = Math.max(...files.map((f) => f.length));
const results = [];
const started = Date.now();

for (const file of files) {
  const res = await runProcess(process.execPath, [path.join('scripts', file)], { cwd: ROOT, timeoutMs });
  let status = 'ok';
  if (res.timedOut) status = 'timeout';
  else if (res.code !== 0) status = 'fail';
  results.push({ file, status, ms: res.ms, output: res.output });
  const label = { ok: 'OK', fail: 'FAIL', timeout: 'TIMEOUT' }[status];
  const note = status === 'timeout' ? `  killed after ${seconds(timeoutMs)}` : '';
  console.log(`  ${file.padEnd(width)}  ${label.padEnd(9)}  ${seconds(res.ms).padStart(7)}${note}`);
}

const total = Date.now() - started;
const failed = results.filter((r) => r.status !== 'ok');
const passed = results.filter((r) => r.status === 'ok');

for (const r of failed) {
  console.log('');
  console.log(rule('-'));
  console.log(
    r.status === 'timeout'
      ? `${r.file}: did not finish in ${seconds(timeoutMs)} and was killed. Last lines:`
      : `${r.file}: failed. Last lines:`,
  );
  for (const line of tail(r.output, 25)) console.log(`  ${line}`);
}

console.log('');
console.log(rule());
console.log(`JS tests: ${passed.length} OK, ${failed.length} failed, in ${duration(total)}`);
if (failed.length) {
  console.log(`  Failed: ${failed.map((r) => r.file + (r.status === 'timeout' ? ' (timeout)' : '')).join(', ')}`);
  console.log('RESULT: FAILED');
  process.exit(1);
}
console.log('TODO OK');
