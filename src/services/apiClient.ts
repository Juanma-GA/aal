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
//
// E17: a call on a material (/materials/<id>/…) carries the change
// authorization chosen for it in the CONFUNFIS (src/stores/uiStore.ts) as
// X-Change-Authorization; the server decides whether it is needed.
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { ApiError, isErrorDetail } from './apiError';
import { refreshAccessToken } from './session';

export { ApiError } from './apiError';
export type { ApiErrorDetail } from './apiError';

export const CHANGE_AUTHORIZATION_HEADER = 'X-Change-Authorization';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';

async function send(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const material = /^\/materials\/([0-9a-f-]{36})\//.exec(path)?.[1];
  const authorization = material ? useUiStore.getState().changeAuthorizations[material] : undefined;
  if (authorization) headers.set(CHANGE_AUTHORIZATION_HEADER, authorization);
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

/** The response of a call, after one refresh-and-retry on a 401; a
 *  refused call is thrown as ApiError. */
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let response = await send(path, init, useAuthStore.getState().accessToken);
  if (response.status === 401 && !NO_RETRY.includes(path)) {
    if (await refreshAccessToken()) {
      response = await send(path, init, useAuthStore.getState().accessToken);
    }
    if (response.status === 401) useAuthStore.getState().signOut();
  }
  if (!response.ok) throw await errorFromResponse(response);
  return response;
}

export async function apiFetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** A file the server answers (an Excel export), with the name it gives. */
export async function apiFetchFile(path: string): Promise<{ blob: Blob; fileName: string | null; headers: Headers }> {
  const response = await apiFetch(path);
  const disposition = response.headers.get('Content-Disposition') ?? '';
  return { blob: await response.blob(), fileName: /filename="([^"]+)"/.exec(disposition)?.[1] ?? null, headers: response.headers };
}

/** A file sent as multipart/form-data (the browser sets the boundary). */
export function apiUpload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append('file', file);
  return apiFetchJson<T>(path, { method: 'POST', body });
}

export function apiSend<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown): Promise<T> {
  return apiFetchJson<T>(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
