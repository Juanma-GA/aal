// Getting a new access token from the refresh cookie (D4).
//
// The server rotates the refresh token on every use and treats a rotated
// token that comes back as stolen (it revokes the whole session). So two
// refreshes must never race with the same cookie:
//   - in one tab, every caller shares the refresh in flight;
//   - across tabs, the Web Locks API runs them one after another, so the
//     second one already sends the cookie the first one received.
// Nothing is stored in the browser for this (HR1): the cookie is HttpOnly
// and the token stays in memory.
import { useAuthStore } from '@/stores/authStore';
import { ApiError } from './apiError';

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';
const LOCK_NAME = 'aal-session-refresh';

interface TokenResponse {
  access_token: string;
}

let inFlight: Promise<boolean> | null = null;

async function requestRefresh(): Promise<boolean> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' });
  } catch {
    // The server did not answer: the session is unknown, not gone. The
    // caller shows a connection error; nothing is signed out.
    throw new ApiError(0, { code: 'network_error' });
  }
  if (response.status >= 500) throw new ApiError(response.status, { code: 'http_error', status: response.status });
  if (!response.ok) {
    useAuthStore.getState().signOut();
    return false;
  }
  const body = (await response.json()) as TokenResponse;
  useAuthStore.getState().signIn(body.access_token);
  return true;
}

async function withLock(task: () => Promise<boolean>): Promise<boolean> {
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined;
  if (!locks) return task();
  return await locks.request(LOCK_NAME, task);
}

/** true: a fresh access token is in the store. false: no session.
 *  Throws an ApiError when the server could not be asked. */
export function refreshAccessToken(): Promise<boolean> {
  if (!inFlight) {
    inFlight = withLock(requestRefresh).finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}
