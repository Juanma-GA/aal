// Global UI state only (D2): what the interface looks like right now, never
// data -- server state lives in React Query. No `persist` middleware: this
// state is never stored in the browser (HR1); what must survive a reload
// (the folded sidebar groups) is saved to the user's ui_preferences on the
// server (src/hooks/useSidebarGroups.ts).
import { create } from 'zustand';

export interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  /** Codes of the sidebar groups the user folded. */
  collapsedGroups: string[];
  setCollapsedGroups: (codes: string[]) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  collapsedGroups: [],
  setCollapsedGroups: (codes) => set({ collapsedGroups: codes }),
}));
