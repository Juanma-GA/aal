// The sentence for an ApiError: its code translated (errors.<code> in the
// locale file), or -- for a code the locale does not know -- the code
// humanized (HR21), never shown raw.
import type { TFunction } from 'i18next';
import { humanize } from '@/lib/humanize';
import { ApiError } from './apiClient';

export interface ErrorMessage {
  message: string;
  reference: string | null;
}

export function describeApiError(error: unknown, t: TFunction): ErrorMessage {
  const detail = error instanceof ApiError ? error.detail : { code: 'network_error' };
  const key = `errors.${detail.code}`;
  const message = t(key, { ...detail, defaultValue: '' }) || t('errors.unknown', { code: humanize(detail.code) });
  return { message, reference: detail.ref ? t('errors.ref', { ref: detail.ref }) : null };
}
