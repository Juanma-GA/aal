import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { fetchMe } from '@/services/authApi';
import { refreshAccessToken } from '@/services/session';
import { useAuthStore } from '@/stores/authStore';
import type { Me } from '@/types/auth';

export const meKey = ['auth', 'me'] as const;

/** Once, when the app loads: a silent refresh recovers the session from
 *  the HttpOnly cookie (the access token was only in memory). */
export function useSessionBootstrap(): void {
  useEffect(() => {
    if (useAuthStore.getState().status !== 'checking') return;
    refreshAccessToken().catch(() => {
      // The server did not answer: show the login page; signing in will
      // report the connection problem.
      useAuthStore.getState().signOut();
    });
  }, []);
}

export function useMe() {
  const status = useAuthStore((s) => s.status);
  return useQuery<Me>({ queryKey: meKey, queryFn: fetchMe, enabled: status === 'signedIn', staleTime: 60_000 });
}
