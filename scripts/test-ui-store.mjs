// The UI store (src/stores/uiStore.ts): plain Zustand, state in memory
// only (HR1 -- scripts/test-no-browser-storage.mjs checks there is no
// persist middleware).
// Run: node scripts/test-ui-store.mjs
import { useUiStore } from '../src/stores/uiStore.ts';

let failures = 0;
function check(name, ok) {
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}`);
  }
}
const store = useUiStore;
check('the sidebar starts open', store.getState().sidebarOpen === true);
store.getState().toggleSidebar();
check('toggle closes it', store.getState().sidebarOpen === false);
store.getState().toggleSidebar();
check('toggle opens it again', store.getState().sidebarOpen === true);
store.getState().setSidebarOpen(false);
check('setSidebarOpen(false)', store.getState().sidebarOpen === false);
check('the store has no persist API', !('persist' in store));
console.log(`${5 - failures}/5 checks passed`);
process.exit(failures ? 1 : 0);
