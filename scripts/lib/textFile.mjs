// Text files read by the checks, the same however git checked them out (on
// Windows git usually writes CRLF): UTF-8, without a BOM, newlines
// normalized. Adapted from brdp-manager.
//
//   normalizeNewlines(text)  CRLF and lone CR -> LF
//   readTextFile(file)       a path or a file: URL; never URL.pathname,
//                            which on Windows is "/C:/..."
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

export function normalizeNewlines(text) {
  return String(text).replace(/\r\n?/g, '\n');
}

export function toPath(file) {
  if (file instanceof URL) return fileURLToPath(file);
  if (typeof file === 'string' && file.startsWith('file:')) return fileURLToPath(file);
  return file;
}

export function readTextFile(file) {
  return normalizeNewlines(fs.readFileSync(toPath(file), 'utf8').replace(/^\uFEFF/, ''));
}
