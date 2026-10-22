// The error every failed API call ends in: the HTTP status and the server's
// sanitized detail ({code, ref, ...params}); status 0 when the server could
// not be reached (code "network_error").

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

export function isErrorDetail(value: unknown): value is ApiErrorDetail {
  return typeof value === 'object' && value !== null && typeof (value as { code?: unknown }).code === 'string';
}
