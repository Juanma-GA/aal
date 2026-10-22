// HR15 / HR8 / design system: in the app's components (src/**/*.tsx)
//   1. no visible text written in the JSX -- it comes from the locale files
//      through t() (HR15); also the visible attributes (alt, title,
//      placeholder, aria-label);
//   2. no raw colour -- no hex, rgb(), hsl(), oklch() and no Tailwind
//      palette colour (bg-white, text-red-500, bg-[#...]): only the
//      semantic token classes of src/styles/globals.css (bg-primary,
//      text-muted-foreground...).
// The scanners are checked on their own fixtures first.
//
// Run: node scripts/test-ui-text.mjs
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

const lineOf = (code, index) => code.slice(0, index).split('\n').length;

// Text between a tag's ">" and the next "<" that has a letter in it. A ">"
// of "=>" or of a comparison is not a tag end.
const JSX_TEXT = /(?<![=-])>([^<>{}]*\p{L}[^<>{}]*)<(?=[/\p{L}])/gu;
const VISIBLE_ATTR = /\b(alt|title|placeholder|aria-label|aria-description|label)\s*=\s*["'`]/g;

export function hardcodedText(source) {
  const code = stripComments(source);
  const found = [];
  for (const m of code.matchAll(JSX_TEXT)) {
    // TypeScript, not JSX text: code punctuation, or a type operator after a
    // generic (ComponentProps<'span'> & VariantProps<...>).
    if (/[;=()]/.test(m[1]) || /^\s*[&|,]/.test(m[1])) continue;
    found.push({ line: lineOf(code, m.index), text: m[1].trim() });
  }
  for (const m of code.matchAll(VISIBLE_ATTR)) found.push({ line: lineOf(code, m.index), text: m[0] });
  return found;
}

const PALETTE = 'white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose';
const RAW_COLOUR = [
  { what: 'a hex colour', re: /#[0-9a-fA-F]{3,8}\b/ },
  { what: 'a colour function', re: /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\(/ },
  { what: 'a Tailwind palette colour', re: new RegExp(`\\b(?:bg|text|border|ring|outline|fill|stroke|from|to|via|shadow|divide|placeholder|decoration|caret|accent)-(?:${PALETTE})(?:-\\d{2,3})?\\b`) },
  { what: 'an arbitrary colour value', re: /-\[(?:#|rgb|hsl|oklch)/ },
];

export function rawColours(source) {
  const code = stripComments(source);
  return code.split('\n').flatMap((line, i) => RAW_COLOUR.filter((r) => r.re.test(line)).map((r) => ({ line: i + 1, what: r.what })));
}

// ── The scanners on their own fixtures ───────────────────────────────────
check('flags JSX text', hardcodedText('return <p>API conectada</p>;').length === 1);
check('flags JSX text with accents', hardcodedText('<span>Versión</span>').length === 1);
check('flags an alt text', hardcodedText('<img alt="Logo em&e" />').length === 1);
check('flags an aria-label', hardcodedText("<button aria-label='Cerrar'>{x}</button>").length === 1);
check('t() is fine', hardcodedText("<p>{t('status.connected')}</p>").length === 0);
check('alt={t()} is fine', hardcodedText("<img alt={t('app.logoAlt')} />").length === 0);
check('an arrow function is fine', hardcodedText('const f = () => a < b;').length === 0);
check('generics are fine', hardcodedText('const s = useState<string>(x); const m = new Map<string, Row>();').length === 0);
check('an object literal after a JSX value is fine', hardcodedText('icons={{ a: <X />,\n info: <Y /> }}').length === 0);
check('a type intersection after a generic is fine', hardcodedText("React.ComponentProps<'span'> &\n  VariantProps<typeof v>").length === 0);
check('a comment is fine', hardcodedText('// <p>Texto</p>').length === 0);
check('flags a hex', rawColours('<div style={{ color: "#2E74B5" }} />').length === 1);
check('flags bg-white', rawColours('className="bg-white p-2"').length === 1);
check('flags text-red-500', rawColours('className="text-red-500"').length === 1);
check('flags bg-[#fff]', rawColours('className="bg-[#fff]"').length >= 1);
check('flags oklch()', rawColours("const c = 'oklch(0.5 0.1 250)';").length === 1);
check('tokens are fine', rawColours('className="bg-primary text-primary-foreground border-border bg-destructive/90"').length === 0);
check('whitespace-nowrap is fine', rawColours('className="whitespace-nowrap"').length === 0);

// ── Every component ──────────────────────────────────────────────────────
const files = walk(SRC, /\.(tsx|ts)$/);
check('scans src/', files.length >= 10, String(files.length));
for (const file of files) {
  const rel = path.relative(ROOT, file).split(path.sep).join('/');
  const source = fs.readFileSync(file, 'utf8');
  if (file.endsWith('.tsx')) {
    for (const hit of hardcodedText(source)) check(`${rel}:${hit.line}: visible text outside the locale files`, false, hit.text);
  }
  for (const hit of rawColours(source)) check(`${rel}:${hit.line}: ${hit.what} (use a token class)`, false);
}

console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
