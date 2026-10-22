// HR21: a machine token (snake_case, kebab-case, camelCase, an enum key or
// a status slug) is never shown as is. humanize() turns it into readable
// text: separators become spaces, camelCase is split, the first letter is
// upper case and the rest lower case -- except words written all in
// capitals (SNS, NOC, CUF), which are acronyms and stay as they are.
//
//   humanize('database_unavailable')  -> 'Database unavailable'
//   humanize('en-revision')           -> 'En revision'
//   humanize('materialSubcategory')   -> 'Material subcategory'
//   humanize('SNS_code')              -> 'SNS code'

export function humanize(token: string): string {
  const words = token
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .split(/[\s_\-.]+/)
    .filter(Boolean)
    .map((word) => (word.length > 1 && word === word.toUpperCase() ? word : word.toLowerCase()));
  if (!words.length) return '';
  const [first, ...rest] = words;
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ');
}
