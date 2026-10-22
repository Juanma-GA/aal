// The session in the browser (D4): the access token lives ONLY here, in
// memory. No `persist` middleware (HR1): a reload loses it and the app
// gets a new one from the HttpOnly refresh cookie (src/services/session.ts).
import { create } from 'zustand';

export type SessionStatus = 'checking' | 'signedIn' | 'signedOut';

export interface AuthState {
  status: SessionStatus;
  accessToken: string | null;
  signIn: (accessToken: string) => void;
  signOut: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  status: 'checking',
  accessToken: null,
  signIn: (accessToken) => set({ status: 'signedIn', accessToken }),
  signOut: () => set({ status: 'signedOut', accessToken: null }),
}));
