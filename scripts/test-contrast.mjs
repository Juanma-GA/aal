// WCAG 2.2 AA for the theme (src/styles/globals.css): every text/background
// pair the app uses at least 4.5:1 (normal text) and every status icon at
// least 3:1 (non-text contrast), in the light and the dark theme, with each
// variant (C, the default, and A). The link (E11) on the background
// and on cards, and distinct from the text next to it. (E15b)
//
// Run: node scripts/test-contrast.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readTextFile } from './lib/textFile.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const css = readTextFile(path.join(ROOT, 'src', 'styles', 'globals.css'));
const TEXT = 4.5;
const ICON = 3;

function block(selector) {
  const start = css.indexOf(`\n${selector} {`);
  if (start < 0) throw new Error(`${selector} not found`);
  return css.slice(start, css.indexOf('}', start));
}

/** Every `--name: oklch(L C H)` of a block (alpha values, like the overlay, aside). */
function tokens(scope) {
  const out = {};
  for (const m of scope.matchAll(/--([\w-]+):\s*oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)/g)) out[m[1]] = m.slice(2).map(Number);
  return out;
}

// OKLCH -> linear sRGB (Björn Ottosson's OKLab).
function luminance([l, c, h]) {
  const a = c * Math.cos((h * Math.PI) / 180);
  const b = c * Math.sin((h * Math.PI) / 180);
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const clamp = (v) => Math.min(1, Math.max(0, v));
  const r = clamp(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_);
  const g = clamp(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_);
  const bl = clamp(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_);
  return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
}

const ratio = (x, y) => {
  const [hi, lo] = [luminance(x), luminance(y)].sort((p, q) => q - p);
  return (hi + 0.05) / (lo + 0.05);
};

// [text or icon, on, minimum]: what the components put on what.
const PAIRS = [
  ['foreground', 'background', TEXT],
  ['card-foreground', 'card', TEXT],
  ['popover-foreground', 'popover', TEXT],
  ['primary-foreground', 'primary', TEXT],
  ['secondary-foreground', 'secondary', TEXT],
  ['muted-foreground', 'muted', TEXT],
  ['muted-foreground', 'background', TEXT],
  ['muted-foreground', 'card', TEXT],
  ['muted-foreground', 'accent', TEXT],
  ['accent-foreground', 'accent', TEXT],
  ['destructive-foreground', 'destructive', TEXT],
  ['destructive', 'card', TEXT],
  ['success-foreground', 'success', TEXT],
  ['warning-foreground', 'warning', TEXT],
  ['warning', 'card', TEXT],
  ['brand-foreground', 'brand', TEXT],
  ['link', 'background', TEXT],
  ['link', 'card', TEXT],
  ['link', 'accent', TEXT],
  // The active tab: primary text on the card.
  ['primary', 'card', TEXT],
  ['info-soft-foreground', 'info-soft', TEXT],
  ['warning-soft-foreground', 'warning-soft', TEXT],
  ['header-foreground', 'header', TEXT],
  ['header-control-foreground', 'header', TEXT],
  ['header-control-foreground', 'header-accent', TEXT],
  ['sidebar-foreground', 'sidebar', TEXT],
  ['sidebar-label', 'sidebar', TEXT],
  ['sidebar-accent-foreground', 'sidebar-accent', TEXT],
  ['sidebar-active-foreground', 'sidebar-active', TEXT],
  ['sidebar-active-bar', 'sidebar-active', ICON],
  ['header-line', 'background', ICON],
  ['sidebar-primary-foreground', 'sidebar-primary', TEXT],
  ['sidebar-primary', 'sidebar', ICON],
  ['sidebar-primary', 'sidebar-accent', ICON],
  ['module-available', 'card', ICON],
  ['module-developing', 'card', ICON],
  ['module-planned', 'card', ICON],
  ['sidebar-module-available', 'sidebar', ICON],
  ['sidebar-module-available', 'sidebar-active', ICON],
  ['sidebar-module-developing', 'sidebar', ICON],
  ['sidebar-module-planned', 'sidebar', ICON],
  ['brand', 'accent', ICON],
  ['ring', 'background', ICON],
];

const root = tokens(block(':root'));
const dark = { ...root, ...tokens(block('.dark')) };
const THEMES = [
  ['light C', root],
  ['light A', { ...root, ...tokens(block(':root:not(.dark)[data-theme-variant="a"]')) }],
  ['dark C', dark],
  ['dark A', { ...dark, ...tokens(block('.dark[data-theme-variant="a"]')) }],
];

let failures = 0;
for (const [theme, t] of THEMES) {
  for (const [fg, bg, min] of PAIRS) {
    if (!t[fg] || !t[bg]) throw new Error(`${theme}: --${!t[fg] ? fg : bg} not found`);
    const value = ratio(t[fg], t[bg]);
    if (value < min) {
      failures += 1;
      console.log(`FAIL ${theme}: ${fg} on ${bg} ${value.toFixed(2)}:1 (needs ${min}:1)`);
    }
  }
  // A link must not look like the plain text next to it.
  console.log(`${theme}: ${PAIRS.length} pairs checked; link vs text ${ratio(t.link, t.foreground).toFixed(2)}:1 (distinct hue)`);
}
console.log(failures ? `${failures} pairs below AA` : 'all pairs AA');
process.exit(failures ? 1 : 0);
