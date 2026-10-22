// Global UI state only (D2): what the interface looks like right now, never
// data -- server state lives in React Query. No `persist` middleware: this
// state is never stored in the browser (HR1); a preference that must
// survive a reload goes to the server.
import { create } from 'zustand';

export interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
