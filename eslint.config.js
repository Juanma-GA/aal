import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import { defineConfig, globalIgnores } from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// Names starting with "_" and an object rest that leaves a field out on
// purpose are not reported as unused.
const UNUSED_VARS = {
  ignoreRestSiblings: true,
  argsIgnorePattern: '^_',
  varsIgnorePattern: '^_',
  caughtErrorsIgnorePattern: '^_',
};

export default defineConfig([
  globalIgnores(['dist', 'backend', 'aacf', 'public', 'private', 'coverage']),
  // The app (TypeScript, browser).
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommended, reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
    languageOptions: { globals: globals.browser },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', UNUSED_VARS],
      // HR1: never browser storage for state (scripts/test-no-browser-storage.mjs
      // checks the same, comments included).
      'no-restricted-globals': ['error', 'localStorage', 'sessionStorage'],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'localStorage' },
        { object: 'window', property: 'sessionStorage' },
      ],
      'no-restricted-imports': ['error', { paths: [{ name: 'zustand/middleware', importNames: ['persist'], message: 'HR1: no persisted UI state.' }] }],
    },
  },
  // shadcn/ui components export their variants next to the component.
  {
    files: ['src/components/ui/**/*.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  // Node: scripts and config files.
  {
    files: ['scripts/**/*.{js,mjs}', '*.{js,mjs}'],
    extends: [js.configs.recommended],
    // Browser globals too: verify-*.mjs pass functions to page.evaluate().
    languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: { ...globals.node, ...globals.browser } },
    rules: { 'no-unused-vars': ['error', UNUSED_VARS] },
  },
  {
    files: ['*.ts'],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    languageOptions: { globals: globals.node },
  },
]);
