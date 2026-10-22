// Toasts for a mutation the server refused (HR20: the optimistic change was
// already rolled back). A version conflict (409, D10) explains itself and
// offers to reload the data.
import type { TFunction } from 'i18next';
import { toast } from 'sonner';
import { ApiError } from '@/services/apiClient';
import { describeApiError } from '@/services/apiErrors';

export function notifyError(error: unknown, t: TFunction, reload?: () => void): void {
  if (error instanceof ApiError && error.detail.code === 'version_conflict') {
    toast.error(t('errors.version_conflict'), {
      description: t('errors.versionConflictHint'),
      action: reload ? { label: t('actions.reload'), onClick: reload } : undefined,
    });
    return;
  }
  const { message, reference } = describeApiError(error, t);
  toast.error(message, { description: reference ?? undefined });
}
