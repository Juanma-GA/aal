// HR1: no browser storage for state. Nothing under src/ uses localStorage
// or sessionStorage (code or comments: the names must not appear at all,
// as in brdp-manager), and no Zustand store uses the `persist` middleware.
// ESLint blocks the same in code (eslint.config.js); this check also covers
// what a lint disable comment would hide.
//
// Run: node scripts/test-no-browser-storage.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripComments, walk } from './lib/sourceScan.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = path.join(ROOT, 'src');
let checks = 0;
let failures = 0;
function check(name, ok, detail = '') {
  checks += 1;
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}${detail ? ` -- ${detail}` : ''}`);
  }
}

const STORAGE = /\b(localStorage|sessionStorage)\b/;
const PERSIST = /\bpersist\s*\(|from\s+['"]zustand\/middleware['"]/;

export function storageUses(source) {
  return source.split('\n').flatMap((line, i) => (STORAGE.test(line) ? [i + 1] : []));
}

export function persistUses(source) {
  return stripComments(source).split('\n').flatMap((line, i) => (PERSIST.test(line) ? [i + 1] : []));
}

// ── The scanner on its own fixtures ──────────────────────────────────────
check('flags localStorage', storageUses('const v = localStorage.getItem("x");').length === 1);
check('flags window.sessionStorage', storageUses('window.sessionStorage.setItem("a", "b");').length === 1);
check('flags persist()', persistUses("import { persist } from 'zustand/middleware';\ncreate(persist((set) => ({}), { name: 'x' }));").join() === '1,2');
check('a plain store is fine', persistUses("import { create } from 'zustand';\ncreate((set) => ({ open: true }));").length === 0);
check('the word persistence in a comment is fine', persistUses('// persist (later) on the server').length === 0);

// ── Every file under src/ ────────────────────────────────────────────────
const files = walk(SRC, /\.(ts|tsx|js|jsx)$/);
check('scans src/', files.length >= 10, String(files.length));
for (const file of files) {
  const rel = path.relative(ROOT, file).split(path.sep).join('/');
  const source = fs.readFileSync(file, 'utf8');
  const storage = storageUses(source);
  check(`${rel}: no localStorage/sessionStorage`, storage.length === 0, `line(s) ${storage.join(', ')}`);
  const persist = persistUses(source);
  check(`${rel}: no Zustand persist`, persist.length === 0, `line(s) ${persist.join(', ')}`);
}

console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
