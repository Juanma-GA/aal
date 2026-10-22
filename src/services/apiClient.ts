// The one way the frontend talks to the backend. Base `/api` (VITE_API_BASE),
// proxied by Vite to FastAPI on port 8000 in development and by nginx in
// production. A failed call always ends in an ApiError with the server's
// sanitized code (app/core/errors.py) and its reference, never a raw
// message; the page translates the code (src/services/apiErrors.ts).
//
// Every call carries the access token from memory (src/stores/authStore.ts).
// On a 401 it asks for a new one once (src/services/session.ts) and repeats
// the call; if there is no session any more the store signs out and the
// route guards send the user to the login page.
import { useAuthStore } from '@/stores/authStore';
import { ApiError, isErrorDetail } from './apiError';
import { refreshAccessToken } from './session';

export { ApiError } from './apiError';
export type { ApiErrorDetail } from './apiError';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';

async function send(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  try {
    return await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'same-origin' });
  } catch {
    throw new ApiError(0, { code: 'network_error' });
  }
}

export async function errorFromResponse(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const detail = (body as { detail?: unknown } | null)?.detail;
  return new ApiError(response.status, isErrorDetail(detail) ? detail : { code: 'http_error', status: response.status });
}

// Routes that answer 401 for their own reasons (a wrong password, no
// session): never retried after a refresh.
const NO_RETRY = ['/auth/login', '/auth/refresh', '/auth/logout'];

export async function apiFetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await send(path, init, useAuthStore.getState().accessToken);
  if (response.status === 401 && !NO_RETRY.includes(path)) {
    if (await refreshAccessToken()) {
      response = await send(path, init, useAuthStore.getState().accessToken);
    }
    if (response.status === 401) useAuthStore.getState().signOut();
  }
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function apiSend<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown): Promise<T> {
  return apiFetchJson<T>(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
