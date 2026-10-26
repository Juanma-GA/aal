// The UI store (src/stores/uiStore.ts): plain Zustand, state in memory
// only (HR1 -- scripts/test-no-browser-storage.mjs checks there is no
// persist middleware).
// Run: node scripts/test-ui-store.mjs
import { useUiStore } from '../src/stores/uiStore.ts';

let failures = 0;
let checks = 0;
function check(name, ok) {
  checks += 1;
  if (!ok) {
    failures += 1;
    console.error(`FAIL ${name}`);
  }
}
const store = useUiStore;
check('the sidebar starts open', store.getState().sidebarOpen === true);
store.getState().setSidebarOpen(false);
check('setSidebarOpen(false)', store.getState().sidebarOpen === false);
check('the width waits for the preferences', store.getState().sidebarWidth === null);
store.getState().setSidebarWidth(320);
check('setSidebarWidth(320)', store.getState().sidebarWidth === 320);
check('the sidebar starts on the left', store.getState().sidebarSide === 'left');
store.getState().setSidebarSide('right');
check('setSidebarSide(right)', store.getState().sidebarSide === 'right');
check('the store has no persist API', !('persist' in store));
console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
