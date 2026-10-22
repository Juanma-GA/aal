// The one way the frontend talks to the backend. Base `/api` (VITE_API_BASE),
// proxied by Vite to FastAPI on port 8000 in development and by nginx in
// production. A failed call always ends in an ApiError with the server's
// sanitized code (app/core/errors.py) and its reference, never a raw
// message; the page translates the code (src/services/apiErrors.ts).

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';

export interface ApiErrorDetail {
  code: string;
  ref?: string;
  [param: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail;

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.code);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function isErrorDetail(value: unknown): value is ApiErrorDetail {
  return typeof value === 'object' && value !== null && typeof (value as { code?: unknown }).code === 'string';
}

export async function apiFetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', ...init.headers },
    });
  } catch {
    throw new ApiError(0, { code: 'network_error' });
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new ApiError(response.status, isErrorDetail(detail) ? detail : { code: 'http_error', status: response.status });
  }
  return body as T;
}
