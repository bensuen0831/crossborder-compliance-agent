import i18n from '../i18n';
import { ApiError } from './client';

export function errorLabel(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return i18n.t('ui.conflictError');
    if (error.status === 0) return i18n.t('ui.networkError');
    return i18n.t('ui.httpError', { status: error.status });
  }
  if (error instanceof Error && i18n.exists(error.message)) return i18n.t(error.message);
  return i18n.t('error');
}
