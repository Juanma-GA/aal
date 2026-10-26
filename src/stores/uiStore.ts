// Global UI state only (D2): what the interface looks like right now, never
// data -- server state lives in React Query. No `persist` middleware: this
// state is never stored in the browser (HR1); what must survive a reload
// (the folded sidebar groups; the sidebar folded, its width and side; the
// detail panel's width, E15) is
// saved to the user's ui_preferences on the server
// (src/hooks/useSidebarGroups.ts, src/hooks/useSidebarLayout.ts).
import { create } from 'zustand';
import type { SidebarSide } from '@/types/auth';

export interface UiState {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  /** Codes of the sidebar groups the user folded. */
  collapsedGroups: string[];
  setCollapsedGroups: (codes: string[]) => void;
  /** The sidebar's width in pixels (null until the preferences load). */
  sidebarWidth: number | null;
  setSidebarWidth: (width: number) => void;
  sidebarSide: SidebarSide;
  setSidebarSide: (side: SidebarSide) => void;
  /** The docked detail panel's width in pixels (E15; null until the preferences load). */
  detailPanelWidth: number | null;
  setDetailPanelWidth: (width: number) => void;
  /** Where a docked detail panel goes (AppLayout's slot beside <main>; null before it renders). */
  detailSlot: HTMLElement | null;
  setDetailSlot: (slot: HTMLElement | null) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  collapsedGroups: [],
  setCollapsedGroups: (codes) => set({ collapsedGroups: codes }),
  sidebarWidth: null,
  setSidebarWidth: (width) => set({ sidebarWidth: width }),
  sidebarSide: 'left',
  setSidebarSide: (side) => set({ sidebarSide: side }),
  detailPanelWidth: null,
  setDetailPanelWidth: (width) => set({ detailPanelWidth: width }),
  detailSlot: null,
  setDetailSlot: (slot) => set({ detailSlot: slot }),
}));
