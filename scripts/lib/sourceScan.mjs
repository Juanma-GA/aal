// Reading the source files the checks scan (Windows safety, HR1, HR15,
// tokens): comments stripped, every file under a folder.
import fs from 'node:fs';
import path from 'node:path';

// Code without comments (line and block) and with string contents kept: a
// comment may mention "/tmp" or ps, the code may not.
export function stripComments(source) {
  let out = '';
  let i = 0;
  let quote = null;
  while (i < source.length) {
    const c = source[i];
    const next = source[i + 1];
    if (quote) {
      out += c;
      if (c === '\\') {
        out += next ?? '';
        i += 2;
        continue;
      }
      if (c === quote) quote = null;
      i += 1;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') {
      quote = c;
      out += c;
      i += 1;
      continue;
    }
    if (c === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') i += 1;
      continue;
    }
    if (c === '/' && next === '*') {
      const end = source.indexOf('*/', i + 2);
      out += source.slice(i, end < 0 ? source.length : end + 2).replace(/[^\n]/g, ' ');
      i = end < 0 ? source.length : end + 2;
      continue;
    }
    out += c;
    i += 1;
  }
  return out;
}

// Every file under `dir` whose name matches `pattern` (node_modules skipped).
export function walk(dir, pattern) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full, pattern));
    else if (pattern.test(entry.name)) out.push(full);
  }
  return out;
}
