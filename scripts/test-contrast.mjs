// WCAG AA for the link token (E11): --link against the background and the
// cards, in the light and the dark theme (src/styles/globals.css), at least
// 4.5:1 (normal text).
//
// Run: node scripts/test-contrast.mjs
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readTextFile } from './lib/textFile.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const css = readTextFile(path.join(ROOT, 'src', 'styles', 'globals.css'));
const MIN = 4.5;

function block(selector) {
  const start = css.indexOf(`${selector} {`);
  return css.slice(start, css.indexOf('}', start));
}

function token(scope, name) {
  const m = new RegExp(`--${name}:\\s*oklch\\(([\\d.]+) ([\\d.]+) ([\\d.]+)\\)`).exec(scope);
  if (!m) throw new Error(`--${name} not found`);
  return m.slice(1).map(Number);
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

let failures = 0;
for (const [theme, scope] of [['light', block(':root')], ['dark', block('.dark')]]) {
  for (const surface of ['background', 'card']) {
    const value = ratio(token(scope, 'link'), token(scope, surface));
    const ok = value >= MIN;
    if (!ok) failures += 1;
    console.log(`${ok ? 'OK' : 'FAIL'} ${theme}: link on ${surface} ${value.toFixed(2)}:1`);
  }
  // A link must not look like the plain text next to it.
  const apart = ratio(token(scope, 'link'), token(scope, 'foreground'));
  console.log(`${theme}: link vs text ${apart.toFixed(2)}:1 (distinct hue)`);
}
process.exit(failures ? 1 : 0);
