// Guards against what only works on Linux in the scripts (adapted from
// brdp-manager): the checks also run on Windows (Node + PowerShell, git
// with CRLF).
//
// 1. A file URL's .pathname is never used as a path: on Windows it is
//    "/C:/Users/...", which fs, path and a child process (Python opened
//    "C:\C:\Users\...") get wrong. fileURLToPath (or the URL object itself,
//    for fs) is the way. .pathname of an http URL (a request's path) is
//    fine and not flagged.
// 2. No hand-written Linux location in code: "/tmp/..." (shot() /
//    os.tmpdir()), backend/.venv/bin/... (scripts/lib/backendPython.mjs),
//    and no program Windows does not have: ps, xmllint, psql, sh/bash.
//    The paths are also checked in the app (src/).
// 3. No script takes a secret as an argument (--password, --token...): it
//    asks for it or reads it from the environment.
// 4. The docs keep the corporate-certificate and PowerShell notes (README.md,
//    docs/instalacion/, CLAUDE.md), CI installs with `npm ci`, and nothing
//    runs `npm audit fix --force`.
//
// The scanner is checked on its own fixtures first (a real Windows bug of
// brdp-manager is flagged, the http uses are not), then run over every
// .mjs/.js under scripts/.
// Run: node scripts/test-windows-safety.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripComments, walk } from './lib/sourceScan.mjs';

const SCRIPTS = path.dirname(fileURLToPath(import.meta.url));
let checks = 0;
let failures = 0;
function check(name, ok, detail = '') {
  checks += 1;
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}${detail ? ` -- ${detail}` : ''}`);
  }
}

const FILE_URL_SOURCE = /import\.meta\.url|pathToFileURL\(|["'`]file:/;

// .pathname uses that come from a file URL: inline (new URL(..., import.meta.url).pathname,
// pathToFileURL(x).pathname) or through a variable assigned from one.
export function filePathnameUses(source) {
  const code = stripComments(source);
  const found = [];
  const lineOf = (index) => code.slice(0, index).split('\n').length;
  const inline = /(?:new URL\([^()]*(?:\([^()]*\)[^()]*)*\)|pathToFileURL\([^()]*\)|import\.meta\.url)\s*\.pathname\b/g;
  for (const m of code.matchAll(inline)) {
    if (m[0].startsWith('new URL(') && !FILE_URL_SOURCE.test(m[0])) continue;
    found.push(lineOf(m.index));
  }
  const assigned = /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;\n]*)/g;
  for (const m of code.matchAll(assigned)) {
    if (!(/new URL\(|pathToFileURL\(/.test(m[2]) && FILE_URL_SOURCE.test(m[2]))) continue;
    const use = new RegExp(`(?<![\\w$.])${m[1].replace(/\$/g, '\\$')}\\.pathname\\b`, 'g');
    for (const u of code.matchAll(use)) found.push(lineOf(u.index));
  }
  return [...new Set(found)].sort((a, b) => a - b);
}

const LINUX_ONLY = [
  { name: 'a hand-written /tmp path (use shot() or os.tmpdir())', re: /["'`]\/tmp(?:\/|["'`])/ },
  { name: 'backend/.venv/bin (use scripts/lib/backendPython.mjs)', re: /\.venv\/bin\// },
  { name: 'the ps program', re: /(?:execFileSync|execFile|spawn|spawnSync)\(\s*["'`]ps["'`]/ },
  { name: 'the psql program (use the backend Python)', re: /(?:execFileSync|execFile|spawn|spawnSync)\(\s*["'`]psql["'`]/ },
  { name: 'a shell (sh/bash) or shell: true', re: /(?:execFileSync|execFile|spawn|spawnSync)\(\s*["'`](?:sh|bash|\/bin\/sh|\/bin\/bash)["'`]|shell:\s*true|\bexecSync\(/ },
];

export function linuxOnlyUses(source) {
  const code = stripComments(source);
  const out = [];
  code.split('\n').forEach((line, i) => {
    for (const rule of LINUX_ONLY) if (rule.re.test(line)) out.push({ line: i + 1, what: rule.name });
  });
  return out;
}

// ── The scanner on its own fixtures ──────────────────────────────────────
{
  // The real line of brdp-manager's test-generate-one-block-per-schema.mjs
  // that broke on Windows.
  const before = [
    'async function roundTrip(file) {',
    '  const path = new URL(`../backend/tests/fixtures/brex/${file}`, import.meta.url);',
    "  const original = fs.readFileSync(path, 'utf8');",
    "  const extracted = extractRules(path.pathname, 'BREX-4.2', 'S1000D 4.2', '4.2');",
    '}',
  ].join('\n');
  check('flags the old .pathname of brdp-manager', filePathnameUses(before).join() === '4', String(filePathnameUses(before)));
  check('fileURLToPath of the same URL is fine', filePathnameUses(before.replace('extractRules(path.pathname', 'extractRules(fileURLToPath(path)')).length === 0);
  check('inline new URL(.., import.meta.url).pathname is flagged', filePathnameUses("const p = new URL('../x.json', import.meta.url).pathname;").length === 1);
  check('import.meta.url .pathname is flagged', filePathnameUses('const here = new URL(import.meta.url).pathname;').length === 1);
  check('pathToFileURL(...).pathname is flagged', filePathnameUses('spawn(py, [pathToFileURL(f).pathname]);').length === 1);
  check('a file: URL literal is flagged', filePathnameUses("const u = new URL('file:///C:/x/y.txt');\nfs.readFileSync(u.pathname);").join() === '2');
  // Legitimate: the path of an http URL.
  check('http: new URL(url).pathname is fine', filePathnameUses('const API_ROUTE = (url) => new URL(url).pathname.startsWith("/api/");').length === 0);
  check('http: a request URL variable is fine', filePathnameUses('const u = new URL(req.url, "http://localhost");\nif (u.pathname === "/api/x") {}').length === 0);
  check('a comment mentioning .pathname is fine', filePathnameUses('// never URL(import.meta.url).pathname').length === 0);
  check('"/tmp/x.png" is flagged', linuxOnlyUses('await page.screenshot({ path: "/tmp/x.png" });').length === 1);
  check('"/tmp" default is flagged', linuxOnlyUses('const SHOTS = process.env.SHOTS_DIR || "/tmp";').length === 1);
  check('.venv/bin is flagged', linuxOnlyUses('execFileSync(".venv/bin/python", args);').length === 1);
  check('ps is flagged', linuxOnlyUses('execFileSync("ps", ["-eo", "pid,args"]);').length === 1);
  check('a comment about /tmp is fine', linuxOnlyUses('// screenshots used to go to "/tmp/x.png"').length === 0);
  check('os.tmpdir() is fine', linuxOnlyUses('path.join(os.tmpdir(), "x.png")').length === 0);
}

// ── Every script ─────────────────────────────────────────────────────────
const self = fileURLToPath(import.meta.url);
const files = walk(SCRIPTS, /\.(m?js)$/).filter((f) => f !== self);
check('scans the scripts', files.length >= 10, String(files.length));
for (const file of files) {
  const rel = path.relative(path.dirname(SCRIPTS), file).split(path.sep).join('/');
  const source = fs.readFileSync(file, 'utf8');
  const lines = filePathnameUses(source);
  check(`${rel}: no file URL .pathname`, lines.length === 0, `line(s) ${lines.join(', ')}: use fileURLToPath`);
  for (const use of linuxOnlyUses(source)) check(`${rel}:${use.line}: ${use.what}`, false);
}

// ── The app: no Linux-only paths either ─────────────────────────────────
const REPO = path.dirname(SCRIPTS);
for (const file of walk(path.join(REPO, 'src'), /\.(ts|tsx|js|jsx)$/)) {
  const rel = path.relative(REPO, file).split(path.sep).join('/');
  for (const use of linuxOnlyUses(fs.readFileSync(file, 'utf8'))) check(`${rel}:${use.line}: ${use.what}`, false);
}

// ── Secrets are never arguments ─────────────────────────────────────────
export function secretArguments(source) {
  const code = stripComments(source);
  const out = [];
  code.split('\n').forEach((line, i) => {
    if (/["'`]--?(?:[\w-]*-)?(?:password|passwd|pwd|secret|token|api-?key)\b/i.test(line)) out.push(i + 1);
  });
  if (/process\.argv/.test(code) && /password|secret|token/i.test(code)) out.push('process.argv with a secret');
  return out;
}
check('flags --password', secretArguments("const i = process.argv.indexOf('--password');").length >= 1);
check('flags --api-token', secretArguments('args: ["--api-token", value]').length === 1);
check('a secret from the environment is fine', secretArguments('const password = process.env.AAL_ADMIN_PASSWORD;').length === 0);
for (const file of files) {
  const rel = path.relative(REPO, file).split(path.sep).join('/');
  for (const hit of secretArguments(fs.readFileSync(file, 'utf8'))) check(`${rel}: ${hit}: a secret as an argument`, false);
}

// ── Docs, CI and dependencies ───────────────────────────────────────────
{
  const read = (rel) => fs.readFileSync(path.join(REPO, ...rel.split('/')), 'utf8');
  for (const rel of ['README.md', 'docs/instalacion/README.md']) {
    const text = read(rel);
    check(`${rel}: "Certificado corporativo" section`, /^## Certificado corporativo$/m.test(text));
    for (const needle of ['UNABLE_TO_GET_ISSUER_CERT_LOCALLY', 'NODE_EXTRA_CA_CERTS', 'npm config set cafile', '--use-system-ca', 'win-ca', 'SSLCertVerificationError', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', '--system-certs', 'UTF-16', 'Read-Host -AsSecureString', 'getpass']) {
      check(`${rel} mentions ${needle}`, text.includes(needle));
    }
  }
  const claude = read('CLAUDE.md');
  for (const needle of ['UTF-16', 'Read-Host -AsSecureString', 'getpass', 'nunca de argumentos', 'Nunca `npm audit fix --force`', '`npm ci`', '--universal']) {
    check(`CLAUDE.md mentions ${needle}`, claude.includes(needle));
  }
  const ci = read('.github/workflows/check.yml');
  check('CI installs with npm ci', /\bnpm ci\b/.test(ci) && !/\bnpm install\b/.test(ci));
  check('CI installs the backend with hashes', /--require-hashes/.test(ci));
  for (const rel of ['.github/workflows/check.yml', 'package.json']) {
    check(`${rel}: no npm audit fix --force`, !/audit fix --force/.test(read(rel)));
  }
}

// ── Line endings: the fixtures are LF on every checkout ─────────────────
{
  const attributes = fs.readFileSync(path.join(REPO, '.gitattributes'), 'utf8');
  check('.gitattributes keeps the backend fixtures LF', /^backend\/tests\/fixtures\/\*\*\s+text eol=lf$/m.test(attributes));
  check('.gitattributes keeps the scripts LF', /^scripts\/\*\*\s+text eol=lf$/m.test(attributes));
}

console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
